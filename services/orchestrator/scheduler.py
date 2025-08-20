import asyncio
import json
import os
import signal
import threading
import time
import uuid

import aiohttp as _aiohttp_lib
import aiosqlite
import httpx
from prometheus_client import Counter, Gauge, Histogram, Summary

from . import store, queue_sqlite
from .queue_sqlite import requeue_orphans
from .schemas import ToolOutput, validate_tool_payload
from collections import defaultdict, deque

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPHTTPSpanExporter
except Exception:
    OTLPHTTPSpanExporter = None

# Metrics window for percentile gauges
METRICS_WINDOW = int(os.getenv('ORCH_METRICS_WINDOW', '500'))

# Prometheus metrics
TOOL_CALLS = Counter('orch_tool_calls_total', 'Total tool calls', [
                     'persona', 'tool', 'status'])
TOOL_TOKENS = Counter('orch_tool_tokens_total',
                      'Total tokens by tool', ['persona', 'tool'])
TOOL_COST = Counter('orch_tool_cost_total',
                    'Total cost by tool', ['persona', 'tool'])
TOOL_LATENCY = Histogram('orch_tool_call_seconds',
                         'Tool call latency seconds', ['persona', 'tool'])

# Percentile gauges (computed over sliding window in-memory)
P50 = Gauge('orch_tool_latency_p50_seconds',
            'p50 latency (sliding window)', ['persona', 'tool'])
P95 = Gauge('orch_tool_latency_p95_seconds',
            'p95 latency (sliding window)', ['persona', 'tool'])
P99 = Gauge('orch_tool_latency_p99_seconds',
            'p99 latency (sliding window)', ['persona', 'tool'])

_latency_windows = defaultdict(lambda: deque(maxlen=METRICS_WINDOW))
_latency_lock = threading.Lock()


def _update_latency_stats(persona, tool, duration):
    key = (persona, tool)
    with _latency_lock:
        dq = _latency_windows[key]
        dq.append(float(duration))
        arr = sorted(dq)

    def pct(arr, q):
        if not arr:
            return 0.0
        idx = int((q/100.0)*(len(arr)-1))
        return arr[idx]
    P50.labels(persona, tool).set(pct(arr, 50))
    P95.labels(persona, tool).set(pct(arr, 95))
    P99.labels(persona, tool).set(pct(arr, 99))


_tracer_initialized = False


def init_tracer():
    global _tracer_initialized
    if _tracer_initialized:
        return trace.get_tracer('orch')
    resource = Resource.create(
        {"service.name": os.getenv("OTEL_SERVICE_NAME", "orchestrator")})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    # Optional: OTLP HTTP exporter if endpoint present
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if endpoint and OTLPHTTPSpanExporter:
        provider.add_span_processor(BatchSpanProcessor(
            OTLPHTTPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    _tracer_initialized = True
    return trace.get_tracer('orch')


ORCH_WORKERS = int(os.getenv('ORCH_WORKERS', '2'))
ORCH_REVISE_MAX = int(os.getenv('ORCH_REVISE_MAX', '2'))

# simple in-memory queue; for multi-instance, replace with Redis/DB-backed queue
_run_queue = asyncio.Queue()
_project_locks = defaultdict(asyncio.Lock)

# Prometheus-style counters (simple in-memory; exposed by /metrics)
_metrics = {
    'run_started_total': 0,
    'run_succeeded_total': 0,
    'run_failed_total': 0,
    'tool_call_duration_seconds_sum': 0.0,
    'tool_call_duration_seconds_count': 0,
}


async def _worker_loop(worker_id: int):
    wid = f"w{worker_id}"
    await queue_sqlite.init()
    while True:
        if await is_draining():
            await asyncio.sleep(0.2)
            continue
        # periodic reaper
        await queue_sqlite.reap_stale(float(os.getenv('ORCH_HEARTBEAT_TIMEOUT', '120')))
        item = await queue_sqlite.claim_next_fair(wid)
        if not item:
            await asyncio.sleep(0.2)
            continue
        run_id = item['run_id']
        plan = item['plan']
        project = item.get('project')
        # per-project lock to avoid interleaving
        lock = _project_locks[project or 'default']
        async with lock:
            ok = True
            try:
                # spawn heartbeat task
                hb_running = True

                async def _hb():
                    while hb_running:
                        await asyncio.sleep(5)
                        try:
                            await queue_sqlite.heartbeat(run_id, wid)
                        except Exception:
                            pass
                hbt = asyncio.create_task(_hb())
                await execute_plan(run_id, plan)
            except Exception:
                ok = False
            finally:
                hb_running = False
                try:
                    hbt.cancel()
                except Exception:
                    pass
                await queue_sqlite.complete(run_id, wid, ok)
                ACTIVE_RUNS.discard(run_id)


# spawn workers on startup (main will call start_workers())
_workers_started = False


async def start_workers(n=ORCH_WORKERS):
    global _workers_started
    if _workers_started:
        return
    for i in range(n):
        asyncio.create_task(_worker_loop(i+1))
    _workers_started = True


def _iter_sse_lines(text: str):
    # naive SSE text parser for 'data: {...}\n\n' events
    for block in text.split('\n\n'):
        if not block.strip():
            continue
        lines = [ln[5:].strip()
                 for ln in block.splitlines() if ln.startswith('data:')]
        if not lines:
            continue
        payload = '\n'.join(lines)
        yield payload


# used when calling other services
ORCH_SERVICE_TOKEN = os.getenv('ORCH_SERVICE_TOKEN', '')
ORCH_RETRY_MAX = int(os.getenv('ORCH_RETRY_MAX', '3'))
# multiplier base seconds
ORCH_RETRY_BACKOFF = float(os.getenv('ORCH_RETRY_BACKOFF', '2.0'))
AGENT_CORE = os.getenv('AGENT_CORE_URL', 'http://localhost:8001')
LEDGER_URL = os.getenv('LEDGER_SERVICE_URL', 'http://localhost:8003')


async def call_tool(persona, tool, payload, timeout=60, idempotency_key=None, expected_schema=None, stream=False, tracer=None):
    tracer = init_tracer()
    from time import time as _now
    _t0 = time.time()
    status_label = 'ok'
    # call agent-core tool endpoint; wrap timings and return result
    url = f"{AGENT_CORE}/tool_{tool}"
    headers = {}
    if ORCH_SERVICE_TOKEN:
        headers['Authorization'] = 'Bearer ' + ORCH_SERVICE_TOKEN
    if idempotency_key:
        headers['Idempotency-Key'] = idempotency_key
    async with httpx.AsyncClient(timeout=timeout) as client:
        with tracer.start_as_current_span(f"tool:{tool}") as span:
            span.set_attribute('persona', persona)
            span.set_attribute('tool', tool)
            span.set_attribute('expected_schema', str(expected_schema))
            span.set_attribute('stream', bool(stream))
        start = time.time()
        try:
            r = await client.post(url, json={'persona': persona, 'payload': payload, 'stream': stream}, headers=headers)
        except Exception as e:
            status_label = 'exception'
            with tracer.start_as_current_span('tool.error') as es:
                es.set_attribute('error', str(e))
            dur = time.time()-start
            TOOL_CALLS.labels(persona, tool, status_label).inc()
            TOOL_LATENCY.labels(persona, tool).observe(dur)
            _update_latency_stats(persona, tool, dur)
            return {'ok': False, 'error': str(e), 'duration': dur}
        duration = time.time()-start
        try:
            j = r.json()
        except Exception:
            # try SSE/JSONL parse to aggregate tokens/cost
            agg = {'tokens': 0, 'cost': 0.0, 'chunks': 0}
            raw = r.text
            # SSE blocks
            for payload_str in _iter_sse_lines(raw):
                try:
                    obj = json.loads(payload_str)
                    agg['tokens'] += int(obj.get('tokens', 0))
                    agg['cost'] += float(obj.get('cost', 0.0))
                    agg['chunks'] += 1
                except Exception:
                    pass
            if agg['chunks'] > 0:
                j = {'stream_summary': agg}
            else:
                # try JSONL
                tokens = 0
                cost = 0.0
                chunks = 0
                for line in raw.splitlines():
                    try:
                        obj = json.loads(line)
                        tokens += int(obj.get('tokens', 0))
                        cost += float(obj.get('cost', 0.0))
                        chunks += 1
                    except Exception:
                        pass
                if chunks > 0:
                    j = {'stream_summary': {'tokens': tokens,
                                            'cost': cost, 'chunks': chunks}}
                else:
                    j = {'raw': raw, 'status': getattr(r, 'status_code', None)}
        # schema validation enforcement if requested: call tool_validate_schema on agent-core
        if expected_schema:
            try:
                vs = await client.post(f"{AGENT_CORE}/tool_validate_schema", json={'schema_name': expected_schema, 'payload': j})
                vres = vs.json() if vs.ok else {'valid': False, 'errors': [
                    {'msg': 'validate_schema call failed', 'status': getattr(vs, 'status_code', None)}]}
                # if invalid, return a specific structure that scheduler can handle
                if not vres.get('valid', False):
                    return {'ok': False, 'error': 'schema_validation_failed', 'validation': vres, 'duration': duration, 'response': j}
            except Exception as e:
                # treat validation failure as non-fatal but flag it
                return {'ok': False, 'error': 'schema_validation_error', 'validation_error': str(e), 'duration': duration, 'response': j}
        # log to ledger if available
        try:
            await client.post(f"{LEDGER_URL}/log_run", json={
                'persona': persona,
                'tool': tool,
                'duration': duration,
                'tokens': j.get('tokens', j.get('token_est', j.get('stream_summary', {}).get('tokens', 0))),
                'cost': j.get('cost', j.get('cost_est', j.get('stream_summary', {}).get('cost', 0.0)))
            }, timeout=5)
        except Exception:
            pass
        # metrics accounting
        status_label = 'ok'
        TOOL_CALLS.labels(persona, tool, status_label).inc()
        TOOL_LATENCY.labels(persona, tool).observe(duration)
        _update_latency_stats(persona, tool, duration)
        tokens_val = j.get('tokens', j.get(
            'token_est', j.get('stream_summary', {}).get('tokens', 0)))
        cost_val = j.get('cost', j.get('cost_est', j.get(
            'stream_summary', {}).get('cost', 0.0)))
        try:
            TOOL_TOKENS.labels(persona, tool).inc(float(tokens_val))
            TOOL_COST.labels(persona, tool).inc(float(cost_val))
        except Exception:
            pass
        return {'ok': True, 'response': j, 'duration': duration, 'status_code': getattr(r, 'status_code', None)}


async def execute_plan(run_id, plan):
    failpoint = os.getenv('ORCH_FAILPOINT', '').strip()
    heartbeat = float(os.getenv('ORCH_HEARTBEAT_SEC', '10'))
    lease_ttl = float(os.getenv('ORCH_LEASE_TTL_SEC', '30'))
    owner = os.getenv('HOSTNAME', 'orchestrator')
    tracer = init_tracer()
    from contextlib import asynccontextmanager
    from time import time as _now
    _t0 = _now()
    # Parent span for the run
    with tracer.start_as_current_span("run") as span:
        ACTIVE_RUNS.add(run_id)
        span.set_attribute('run.id', run_id)
        span.set_attribute('project', plan.get('project', 'default'))

    # enhanced execute_plan with retries, idempotency, resume support

    # plan: dict with 'plan_id' and 'steps' list
    trace = {'steps': []}
    store.update_run_trace(run_id, 'running', trace)
    for step in plan.get('steps', []):
        step_id = step.get('step_id') or str(uuid.uuid4())
        desc = step.get('description', '')
        persona = step.get('persona', 'coder')
        tool = step.get('tool') or step.get('action') or 'generate_code'
        payload = step.get('payload', {})
        idempotency_key = step.get('idempotency_key') or f"{run_id}:{step_id}"
        expected_schema = step.get('expected_schema')
        # check cancellation
        if store.is_cancelled(run_id):
            trace['steps'].append(
                {'step_id': step_id, 'description': desc, 'status': 'cancelled'})
            store.update_run_trace(run_id, 'cancelled', trace)
            return {'ok': False, 'trace': trace, 'cancelled': True}
        # resume: skip steps already with status 'ok'
        existing_steps = trace.get('steps', [])
        matched = next((s for s in existing_steps if s.get(
            'step_id') == step_id and s.get('status') == 'ok'), None)
        if matched:
            # already succeeded, skip
            continue
        # perform retries loop
        attempt = 0
        success = False
        last_err = None
        while attempt < ORCH_RETRY_MAX and not success:
            attempt += 1
            trace['steps'].append({'step_id': step_id, 'description': desc, 'status': 'running',
                                  'attempt': attempt, 'started_at': time.time(), 'persona': persona, 'tool': tool})
            store.update_run_trace(run_id, 'running', trace)
            try:
                res = await call_tool(persona, tool, payload, idempotency_key=idempotency_key, expected_schema=expected_schema)
                trace['steps'][-1].update({'result': res,
                                          'ended_at': time.time()})
                if res.get('ok'):
                    trace['steps'][-1].update({'status': 'ok'})
                    success = True
                    store.update_run_trace(run_id, 'running', trace)
                    break
                else:
                    last_err = res.get('error') or res.get('response')
                    trace['steps'][-1].update({'status': 'error',
                                              'error': last_err})
                    store.update_run_trace(run_id, 'running', trace)
                    # if schema_validation_failed, do not retry - escalate to critic by marking failed
                    if res.get('error') in ('schema_validation_failed', 'schema_validation_error'):
                        store.update_run_trace(run_id, 'failed', trace)
                        return {'ok': False, 'trace': trace, 'error': 'validation'}
            except Exception as e:
                last_err = str(e)
                trace['steps'][-1].update({'status': 'error',
                                          'error': last_err, 'ended_at': time.time()})
                store.update_run_trace(run_id, 'running', trace)
            # backoff before retry
            if not success and attempt < ORCH_RETRY_MAX:
                await asyncio.sleep(ORCH_RETRY_BACKOFF ** attempt)
        if not success:
            store.update_run_trace(run_id, 'failed', trace)
            return {'ok': False, 'trace': trace, 'error': last_err}

    store.update_run_trace(run_id, 'succeeded', trace)
    return {'ok': True, 'trace': trace}


async def queue_run(run_id, plan):
    await start_workers(ORCH_WORKERS)
    await queue_sqlite.enqueue(run_id, plan)
    return {'ok': True, 'queued': True, 'run_id': run_id}


DRAINING = False


async def set_draining(val: bool):
    global DRAINING
    DRAINING = bool(val)


async def is_draining() -> bool:
    return DRAINING


ACTIVE_RUNS = set()


async def active_count():
    return len(ACTIVE_RUNS)


async def wait_for_drain(timeout: float = 20.0):
    t0 = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - t0) < timeout:
        if not ACTIVE_RUNS:
            return True
        await asyncio.sleep(0.2)
    return False


def span_step_attrs(span, run_id: str, step_id: str, project: str):
    if not span:
        return
    span.set_attribute('run.id', run_id)
    if step_id:
        span.set_attribute('step.id', step_id)
    span.set_attribute('project', project or 'default')


METRIC_RETRIES = Counter('orch_retries_total',
                         'Total retries', ['run_id', 'step_id'])
METRIC_VALIDATION_ERRORS = Counter(
    'orch_validation_errors_total', 'Tool validation errors', ['tool', 'schema'])
METRIC_IDEMPOTENT_SKIPS = Counter(
    'orch_idempotent_skips_total', 'Steps skipped because already done', ['run_id', 'step_id'])


def install_signal_handlers(loop):
    def _handler(signum, frame):
        # Best-effort: set draining; active tasks will finish or be requeued by shutdown
        loop.create_task(set_draining(True))
    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


async def start_watchdog():
    interval = float(os.getenv('ORCH_WATCHDOG_SEC', '15'))
    while True:
        try:
            await requeue_orphans()
        except Exception:
            pass
        await asyncio.sleep(interval)


# Histogram buckets tuned for orchestration latencies
ORCH_STEP_DURATION = Histogram("orch_step_duration_seconds", "Duration of a step execution", buckets=[
                               0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60])
ORCH_LEASE_WAIT = Histogram("orch_lease_wait_seconds", "Time spent waiting to acquire a step lease", buckets=[
                            0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5])


# Summaries for client-side quantiles (p50/p90/p99)
ORCH_STEP_DURATION_SUMMARY = Summary(
    "orch_step_duration_seconds_summary", "Step duration summary")
ORCH_LEASE_WAIT_SUMMARY = Summary(
    "orch_lease_wait_seconds_summary", "Lease wait summary")


async def ensure_orch_aux_tables():
    db_path = os.getenv('ORCH_QUEUE_DB', '/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS lease_wait_samples (id INTEGER PRIMARY KEY AUTOINCREMENT, tool TEXT, persona TEXT, seconds REAL, ts INTEGER)")
        # Executions table may already exist; ensure columns for start/end
        try:
            await db.execute("ALTER TABLE executions ADD COLUMN started_at INTEGER")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE executions ADD COLUMN ended_at INTEGER")
        except Exception:
            pass
        await db.commit()

# Schedule table ensure on import
asyncio.get_event_loop().create_task(ensure_orch_aux_tables())
