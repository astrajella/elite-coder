from services.orchestrator.metrics import ORCH_TOOL_CALLS, ORCH_TOOL_LATENCY

import requests, httpx, asyncio, time, os, json
from typing import Any, Dict
from services.common import schemas as _schemas
from services.orchestrator.validation_wrapper import validate, SCHEMA_MAP
from prometheus_client import Counter, Histogram

# metrics (reuse wrapper ones if available)
ORCH_TOOL_CALLS = Counter("orch_tool_calls_total_auto", "Auto instrumented tool calls", ["tool","persona","status","schema_ok"])
ORCH_STEP_LATENCY = Histogram("orch_tool_latency_seconds_auto", "Latency per tool", ["tool","persona"])

_orig_requests_post = requests.post
_orig_httpx_post = httpx.AsyncClient.post

def _extract_tool_from_url(url: str) -> str:
    try:
        return str(url).rstrip('/').split('/')[-1]
    except Exception:
        return "unknown"

def _redact_json(obj):
    if isinstance(obj, dict):
        out = {}
        for k,v in obj.items():
            if any(s in k.lower() for s in ('key','token','secret','password','authorization','api_key','access_token')):
                out[k] = "REDACTED"
            else:
                out[k] = _redact_json(v)
        return out
    elif isinstance(obj, list):
        return [_redact_json(x) for x in obj]
    else:
        return obj

def _validate_and_record(tool, persona, payload):
    schema = SCHEMA_MAP.get(tool)
    try:
        # try local pydantic validation quickly
        if not schema:
            return {"valid": True, "errors": []}
        cls = getattr(_schemas, schema, None)
        if cls is None:
            return {"valid": True, "errors": []}
        cls(**payload)
        return {"valid": True, "errors": []}
    except Exception as e:
        return {"valid": False, "errors": [str(e)]}

def patched_requests_post(url, *args, **kwargs):
    start = time.time()
    persona = kwargs.get('json',{}).get('persona') if isinstance(kwargs.get('json',{}), dict) else None
    tool = _extract_tool_from_url(url)
    resp = _orig_requests_post(url, *args, **kwargs)
    status = "success" if resp.ok else "failure"
    try:
        body = resp.json()
    except Exception:
        body = {"text": resp.text}
    v = _validate_and_record(tool, persona, body if isinstance(body, dict) else {})
    schema_ok = "true" if v.get("valid") else "false"
    ORCH_TOOL_CALLS.labels(tool, persona or "unknown", status, schema_ok).inc()
    ORCH_STEP_LATENCY.labels(tool, persona or "unknown").observe(time.time()-start)
    return resp

async def patched_httpx_post(self, url, *args, **kwargs):
    start = time.time()
    persona = kwargs.get('json',{}).get('persona') if isinstance(kwargs.get('json',{}), dict) else None
    tool = _extract_tool_from_url(url)
    resp = await _orig_httpx_post(self, url, *args, **kwargs)
    status = "success" if getattr(resp, 'status_code', None) and resp.status_code < 400 else "failure"
    try:
        body = resp.json()
    except Exception:
        body = {"text": getattr(resp, 'text', None)}
    v = _validate_and_record(tool, persona, body if isinstance(body, dict) else {})
    schema_ok = "true" if v.get("valid") else "false"
    ORCH_TOOL_CALLS.labels(tool, persona or "unknown", status, schema_ok).inc()
    ORCH_STEP_LATENCY.labels(tool, persona or "unknown").observe(time.time()-start)
    return resp

# apply monkeypatch at import time
try:
    requests.post = patched_requests_post
except Exception:
    pass

try:
    httpx.AsyncClient.post = patched_httpx_post
except Exception:
    pass
