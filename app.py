
import os, uuid, time
from flask import Flask, request, jsonify, g
import structlog
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from werkzeug.middleware.proxy_fix import ProxyFix
from services.schemas import CodePatchList, FilePatch, ErrorResponse

app = Flask(__name__)
# Production cookie defaults
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_HTTPONLY=True
)

# Trust reverse proxy (nginx)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

logger = structlog.get_logger()

REQ_COUNTER = Counter("http_requests_total", "HTTP requests", ["method","endpoint","status"])
REQ_LATENCY = Histogram("http_request_latency_seconds", "HTTP request latency", ["endpoint"])

@app.before_request
def _inject_ctx():
    g.start_time = time.time()
    g.correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    # bind correlation id into logger context
    structlog.contextvars.bind_contextvars(correlation_id=g.correlation_id)

@app.after_request
def _metrics(resp):
    try:
        dt = time.time() - getattr(g, "start_time", time.time())
        REQ_LATENCY.labels(request.path).observe(dt)
        REQ_COUNTER.labels(request.method, request.path, resp.status_code).inc()
        # add correlation id header
        resp.headers["x-correlation-id"] = getattr(g, "correlation_id", "")
    except Exception as e:
        pass
    return resp

@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

import os, json, uuid, zipfile, hashlib, time, subprocess, sys
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from pydantic import ValidationError
from schemas import CodePatchList, ErrorResponse, SummarizerSchema, PlanSchema, TestResultsSchema
from rag_helper import RagStore
from config import settings
import structlog
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_ROOT, "static")
DOCS_DIR = os.path.join(APP_ROOT, "docs")
WORK_DIR = APP_ROOT
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

# structured logging
structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger(service="gateway")
# Prometheus counters/histograms
MET_TOOL_CALLS = Counter("tool_calls_total", "Tool calls", ["tool","status"])
MET_HTTP_LAT = Histogram("http_request_seconds", "HTTP latency", ["route"])

rag = RagStore(settings.RAG_VECTOR_DB_PATH)
if not rag.docs:
    rag.seed_from_folder(DOCS_DIR)

HISTORY = None  # deprecated

def validate(schema_name: str, payload: dict):
    try:
        if schema_name == "CodePatchList":
            obj = CodePatchList(**payload)
        elif schema_name == "SummarizerSchema":
            obj = SummarizerSchema(**payload)
        elif schema_name == "PlanSchema":
            obj = PlanSchema(**payload)
        elif schema_name == "TestResultsSchema":
            obj = TestResultsSchema(**payload)
        else:
            return False, {"error": f"Unknown schema {schema_name}"}
        return True, obj.dict()
    except ValidationError as e:
        return False, json.loads(e.json())

def sse_event(kind, payload):
    return f"event: {kind}\ndata: {json.dumps(payload)}\n\n"

# ---------- Tool Endpoints ----------

@app.post("/tool_retrieve_rag")
def tool_retrieve_rag():
    body = request.get_json(silent=True) or {}
    query = body.get("query","")
    top_k = int(body.get("top_k",3))
    hops = int(body.get("hops",1))
    expansion_k = int(body.get("expansion_k",5))
    try:
        if hasattr(rag, "multi_hop") and hops and hops > 1:
            retrieved = rag.multi_hop(query, top_k=top_k, hops=hops, expansion_k=expansion_k)
        else:
            retrieved = rag.top_k(query, top_k=top_k)
        dim = getattr(rag.store, "dim", None)
        return jsonify({"retrieved": retrieved, "query_embedding_dim": dim or 384, "hops_used": hops})
    except Exception as e:
        logger.error("rag_retrieve_error", error=str(e))
        return jsonify({"error": "Failed to retrieve information"}), 500

    body = request.get_json(silent=True) or {}
    query = body.get("query","")
    top_k = int(body.get("top_k", 3))
    hops = int(body.get("hops", 1))
    expansion_k = int(body.get("expansion_k", 3))
    try:
        if hasattr(rag, "multi_hop") and hops and hops > 1:
            retrieved = rag.multi_hop(query, top_k=top_k, hops=hops, expansion_k=expansion_k)
        else:
            retrieved = rag.top_k(query, top_k=top_k)
        dim = getattr(rag.store, "dim", 384)
        return jsonify({"retrieved": retrieved, "query_embedding_dim": dim, "hops_used": hops})
    except Exception as e:
        app.logger.error({"event":"tool_retrieve_rag_error","error":str(e)})
        return jsonify({"error":"Failed to retrieve information"}), 500


@app.post("/tool_summarize_tokens")
def tool_summarize_tokens():
    body = request.get_json(silent=True) or {}
    blocks = body.get("context_blocks", [])
    max_tokens = int(body.get("max_tokens", 1200))
    joined = "\n\n".join(blocks)
    max_chars = max_tokens * 4
    summary = joined if len(joined) <= max_chars else joined[:max_chars]
    token_est = max(1, len(summary)//4)
    cost_est = (token_est/1000.0)*settings.PRICE_PER_1K_INPUT
    return jsonify({"summary": summary, "tokens_est": token_est, "cost_estimate": cost_est})

@app.post("/tool_plan_step")
def tool_plan_step():
    body = request.get_json(silent=True) or {}
    goal = body.get("goal","")
    plan_id = str(uuid.uuid4())
    steps = [
        {"step_id":"retrieve","description":"RAG retrieve","estimated_effort":"low"},
        {"step_id":"summarize","description":"Summarizer compresses RAG + state","estimated_effort":"low"},
        {"step_id":"code","description":"Coder generates patches","estimated_effort":"med"},
        {"step_id":"validate","description":"Validate patches with Pydantic","estimated_effort":"low"},
        {"step_id":"test","description":"Run tests + lint","estimated_effort":"low"},
        {"step_id":"critic","description":"Critic suggests fixes","estimated_effort":"low"},
        {"step_id":"finalize","description":"Commit & artifact zip","estimated_effort":"low"}
    ]
    return jsonify({"plan_id": plan_id, "steps": steps, "priority": 50})

@app.post("/tool_generate_code")
def tool_generate_code():
    body = request.get_json(silent=True) or {}
    step_id = body.get("step_id", "code")
    files_requested = body.get("files_requested", [])
    patches = []
    for f in files_requested:
        path = f.get("path")
        if not path: continue
        # Defaults by file type
        if path.endswith(".md"):
            content = "# Agent Notes\n\n- Generated by CODER persona.\n"
        elif path.endswith(".js"):
            content = "/* CODER persona output */\nexport const generated = true;\n"
        elif path.endswith(".py"):
            content = "'''CODER persona output'''\nVALUE = 42\n"
        elif path.endswith(".html"):
            content = "<!-- CODER persona output -->\n"
        else:
            content = ""
        patches.append({"path": path, "type": "create", "content": content})
    payload = {"plan_id": body.get("plan_id","plan"), "step_id": step_id, "patches": patches, "author":"coder_agent", "explain": f"{len(patches)} file(s) generated"}
    ok, info = validate("CodePatchList", payload)
    if not ok:
        return jsonify({"valid": False, "errors": info}), 400
    return jsonify(payload)

@app.post("/tool_validate_schema")
def tool_validate_schema():
    body = request.get_json(silent=True) or {}
    schema_name = body.get("schema_name")
    payload = body.get("payload")
    ok, info = validate(schema_name, payload)
    return jsonify({"valid": ok, "errors": None if ok else info})

@app.post("/tool_run_tests")
def tool_run_tests():
    body = request.get_json(silent=True) or {}
    timeout = int(body.get("timeout_sec", 60))
    result = {"passed":0, "failed":0, "failures":[], "logs_url":None}
    # pytest
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", "-q"], capture_output=True, timeout=timeout, text=True)
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        if p.returncode == 0:
            result["passed"] += 1
        else:
            result["failed"] += 1
            result["failures"].append({"test":"pytest", "trace": out[:4000]})
    except Exception as e:
        result["failed"] += 1
        result["failures"].append({"test":"pytest-exec", "trace": str(e)})
    # flake8
    try:
        p2 = subprocess.run(["flake8","."], capture_output=True, timeout=timeout, text=True)
        if p2.returncode != 0:
            result["failed"] += 1
            out2 = (p2.stdout or "") + "\n" + (p2.stderr or "")
            result["failures"].append({"test":"flake8", "trace": out2[:4000]})
        else:
            result["passed"] += 1
    except Exception as e:
        result["failed"] += 1
        result["failures"].append({"test":"flake8-exec", "trace": str(e)})
    return jsonify(result)

@app.post("/tool_critic_review")
def tool_critic_review():
    body = request.get_json(silent=True) or {}
    test_results = body.get("test_results", {})
    if test_results.get("failed",0) > 0:
        return jsonify({"verdict":"revise","notes":"Tests/lint failed. Fix and retry.","fix_recommendations":[{"step_id":"code","patch_request":{"hint":"Resolve flake8 errors and failing tests"}}]})
    return jsonify({"verdict":"accept","notes":"Ready to commit","fix_recommendations":[]})

@app.post("/tool_commit_and_artifact")
def tool_commit_and_artifact():
    body = request.get_json(silent=True) or {}
    patches_payload = body.get("patches")
    cpl = {"plan_id": body.get("plan_id","plan"),
           "step_id": body.get("step_id","step"),
           "patches": patches_payload or [],
           "author": body.get("author","coder_agent"),
           "explain": body.get("explain")}
    ok, info = validate("CodePatchList", cpl)
    if not ok:
        MET_TOOL_CALLS.labels(tool="tool_commit_and_artifact", status="schema_error").inc()
        return jsonify({"code":400, "message":"Schema validation failed on commit", "details": info}), 400

    # apply patches
    for p in cpl["patches"]:
        target = os.path.join(WORK_DIR, p["path"])
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(p["content"])

    commit_id = hashlib.sha1(str(time.time()).encode()).hexdigest()[:12]
    artifact_rel = f"artifacts/artifact_{commit_id}.zip"
    artifact_abs = os.path.join(WORK_DIR, artifact_rel)
    os.makedirs(os.path.dirname(artifact_abs), exist_ok=True)
    with zipfile.ZipFile(artifact_abs, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(WORK_DIR):
            for fn in files:
                if fn.endswith(".zip"): 
                    continue
                full = os.path.join(root, fn)
                arc = os.path.relpath(full, WORK_DIR)
                zf.write(full, arc)
    size = os.path.getsize(artifact_abs)
    artifact_url = f"/static/{artifact_rel}" if app.static_url_path == "/static" else artifact_rel

    # log to ledger
    try:
        from ledger import log_commit
        log_commit(commit_id, {"size": size, "patches": len(cpl["patches"])})
    except Exception as e:
        log.warn("ledger_commit_log_error", error=str(e))

    MET_TOOL_CALLS.labels(tool="tool_commit_and_artifact", status="ok").inc()
    return jsonify({"commit_id": commit_id, "artifact": artifact_rel, "size_bytes": size})
@app.post("/tool_log_and_metrics")
def tool_log_and_metrics():
    body = request.get_json(silent=True) or {}
    level = (body.get("level","info") or "info").upper()
    event = body.get("event","")
    meta = body.get("meta",{})
    print(f"[{level}] {event} :: {meta}")
    return jsonify({"ok": True})

# ---------- Elite: SSE streaming orchestration ----------
@app.get("/sse/run")
def sse_run():
    goal = request.args.get("goal","Build feature")
    top_k = int(request.args.get("top_k","3"))
    def gen():
        yield sse_event("status", {"msg": "retrieve"})
        retrieved = rag.top_k(goal, top_k=top_k)
        yield sse_event("retrieve", {"retrieved": retrieved})
        yield sse_event("status", {"msg": "summarize"})
        joined = "\n\n".join([x["text"] for x in retrieved])
        summary = joined[:3200]
        tokens = max(1, len(summary)//4)
        cost = (tokens/1000.0)*settings.PRICE_PER_1K_INPUT
        yield sse_event("summarize", {"summary": summary, "tokens_est": tokens, "cost_estimate": cost})
        yield sse_event("status", {"msg": "plan"})
        plan_id = str(uuid.uuid4())
        plan = {"plan_id": plan_id, "steps":[{"step_id":"code","description":"generate files","estimated_effort":"med"}], "priority": 50}
        yield sse_event("plan", plan)
        yield sse_event("status", {"msg":"code"})
        patches = [{"path":"docs/ITERATION_NOTES.md","type":"create","content":"# Iteration notes\n"}]
        cpl = {"plan_id": plan_id, "step_id":"code", "patches": patches, "author":"coder_agent"}
        yield sse_event("code", cpl)
        yield sse_event("status", {"msg":"validate"})
        ok, info = validate("CodePatchList", cpl)
        yield sse_event("validate", {"valid": ok, "errors": None if ok else info})
        yield sse_event("status", {"msg":"tests"})
        # simple test run
        try:
            p = subprocess.run([sys.executable, "-m", "pytest", "-q"], capture_output=True, timeout=60, text=True)
            passed = 1 if p.returncode == 0 else 0
            failed = 0 if p.returncode == 0 else 1
            trace = (p.stdout or "") + "\n" + (p.stderr or "")
            yield sse_event("tests", {"passed": passed, "failed": failed, "trace": trace[:2000]})
        except Exception as e:
            yield sse_event("tests", {"passed":0, "failed":1, "trace": str(e)})
        yield sse_event("status", {"msg":"done"})
    return Response(gen(), mimetype='text/event-stream')

# ---------- Extra APIs ----------
@app.get("/api/models")
def api_models():
    return jsonify({
        "default": settings.OPENROUTER_DEFAULT_MODEL,
        "coder": settings.MODEL_CODER,
        "critic": settings.MODEL_CRITIC,
        "summarizer": settings.MODEL_SUMMARIZER,
        "allow_internet": settings.ALLOW_INTERNET
    })

@app.get("/api/history")
def api_history():
    try:
        from ledger import get_history  # assume local helper wired to DB
        rows = get_history(limit=int(request.args.get("limit",50)))
        return jsonify({"items": rows})
    except Exception as e:
        app.logger.error({"event":"history_error","error":str(e)})
        return jsonify({"error":"history unavailable"}), 500


@app.get("/api/artifacts")
def api_artifacts():
    items = []
    for fn in os.listdir(WORK_DIR):
        if fn.startswith("artifact_") and fn.endswith(".zip"):
            p = os.path.join(WORK_DIR, fn)
            items.append({"name": fn, "size": os.path.getsize(p), "path": p})
    return jsonify(items)

@app.get("/api/file")
def api_get_file():
    path = request.args.get("path","")
    if not path:
        return jsonify({"code": 400, "message": "Bad Request"}), 400
    work_dir_abs = os.path.abspath(WORK_DIR)
    safe_path_abs = os.path.abspath(os.path.join(work_dir_abs, path))
    if not safe_path_abs.startswith(work_dir_abs):
        return jsonify({"code": 403, "message": "Forbidden"}), 403
    if not os.path.exists(safe_path_abs) or not os.path.isfile(safe_path_abs):
        return jsonify({"code": 404, "message": "Not found"}), 404
    with open(safe_path_abs, "r", encoding="utf-8", errors="ignore") as f:
        return jsonify({"path": path, "content": f.read()})


@app.post("/api/apply_patches")
def api_apply_patches():
    body = request.get_json(silent=True) or {}
    ok, info = validate("CodePatchList", body)
    if not ok:
        return jsonify({"code":400, "message":"Invalid CodePatchList", "details": info}), 400
    for p in body["patches"]:
        target = os.path.join(WORK_DIR, p["path"])
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(p["content"])
    return jsonify({"ok": True})

@app.post("/api/rag/search")
def api_rag_search():
    body = request.get_json(silent=True) or {}
    q = body.get("q","")
    k = int(body.get("k",3))
    hops = int(body.get("hops",1))
    expansion_k = int(body.get("expansion_k",2))
    if hops and hops>1 and hasattr(rag, 'multi_hop'):
        results = rag.multi_hop(q, top_k=k, hops=hops, expansion_k=expansion_k)
    else:
        results = rag.top_k(q, top_k=k)
    return jsonify({'results': results, 'count': len(results)})
@app.post("/api/rag/add")
def api_rag_add():
    body = request.get_json(silent=True) or {}
    docs = body.get("docs",[])
    rag.add(docs)
    return jsonify({"ok": True, "count": len(rag.docs)})

@app.post("/api/rag/drop")
def api_rag_drop():
    body = request.get_json(silent=True) or {}
    ids = body.get("ids",[])
    rag.drop(ids)
    return jsonify({"ok": True, "count": len(rag.docs)})

@app.get("/static/<path:fn>")
def static_file(fn):
    return send_from_directory(STATIC_DIR, fn)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

from fastapi.responses import StreamingResponse, PlainTextResponse
from ledger import log_run, get_runs, get_stats, get_daily, export_daily_csv
import asyncio, json

@app.get("/ledger")
async def ledger_list(limit:int=100):
    return {"runs":get_runs(limit=limit)}

@app.get("/ledger/stats")
async def ledger_stats():
    return get_stats()

@app.get("/ledger/daily")
async def ledger_daily():
    return {"daily":get_daily()}

@app.get("/ledger/daily/export")
async def ledger_daily_export():
    csv_data=export_daily_csv()
    return PlainTextResponse(csv_data,media_type="text/csv")

@app.get("/ledger/stream")
async def ledger_stream():
    async def event_generator():
        while True:
            await asyncio.sleep(5)
            data=json.dumps(get_stats())
            yield f"data: {data}\n\n"
    return StreamingResponse(event_generator(),media_type="text/event-stream")

@app.get("/ledger/runs/export")
async def ledger_runs_export():
    csv_data=export_runs_csv()
    return PlainTextResponse(csv_data,media_type="text/csv")


@app.get("/metrics")
def metrics():
    data = generate_latest()
    return Response(response=data, status=200, mimetype=CONTENT_TYPE_LATEST)


@app.get("/metrics")
def metrics():
    data = generate_latest()
    from flask import Response
    return Response(data, mimetype=CONTENT_TYPE_LATEST)
