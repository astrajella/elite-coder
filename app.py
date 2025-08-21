
import os, uuid, time, json, zipfile, hashlib, subprocess, sys
from flask import Flask, request, jsonify, g, send_from_directory, Response
from flask_cors import CORS
import structlog
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from werkzeug.middleware.proxy_fix import ProxyFix
from pydantic import ValidationError
from schemas import CodePatchList, ErrorResponse, SummarizerSchema, PlanSchema, TestResultsSchema, FilePatch
from rag_helper import RagStore
from config import settings

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
        logger.error("Failed to record metrics", exc_info=e)
    return resp

@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


APP_ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_ROOT, "static")
DOCS_DIR = os.path.join(APP_ROOT, "docs")
WORK_DIR = APP_ROOT
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)


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

# ---------- Elite: SSE streaming orchestration ----------
@app.get("/sse/run")
def sse_run():
    goal = request.args.get("goal","Build feature")
    try:
        top_k = int(request.args.get("top_k","3"))
    except ValueError:
        return Response(sse_event("error", {"msg": "top_k must be an integer"}), mimetype='text/event-stream', status=400)

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
        limit = int(request.args.get("limit",50))
        rows = get_history(limit=limit)
        return jsonify({"items": rows})
    except ValueError:
        return jsonify({"code": 400, "message": "limit parameter must be an integer"}), 400
    except Exception as e:
        app.logger.error({"event":"history_error","error":str(e)})
        return jsonify({"error":"history unavailable"}), 500


@app.get("/api/artifacts")
def api_artifacts():
    items = []
    try:
        for fn in os.listdir(WORK_DIR):
            if fn.startswith("artifact_") and fn.endswith(".zip"):
                p = os.path.join(WORK_DIR, fn)
                try:
                    items.append({"name": fn, "size": os.path.getsize(p), "path": p})
                except FileNotFoundError:
                    # File might have been deleted between listdir and getsize, just skip it
                    logger.warning("artifact_file_disappeared", path=p)
                    continue
    except OSError as e:
        logger.error("artifacts_error", error=str(e))
        return jsonify({"error": "cannot list artifacts"}), 500
    return jsonify(items)


@app.post("/api/apply_patches")
def api_apply_patches():
    body = request.get_json(silent=True) or {}
    ok, info = validate("CodePatchList", body)
    if not ok:
        return jsonify({"code":400, "message":"Invalid CodePatchList", "details": info}), 400

    for p in body.get("patches", []):
        path = p.get("path")
        if not path:
            # Skip patches with no path
            continue

        target_path = os.path.abspath(os.path.join(WORK_DIR, path))

        # Security: Ensure the path is within the working directory
        if not target_path.startswith(os.path.abspath(WORK_DIR)):
            log.warning("path_traversal_attempt", requested_path=path)
            return jsonify({"code": 400, "message": f"Path traversal attempt blocked for path: {path}"}), 400

        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(p.get("content", ""))
        except IOError as e:
            log.error("file_write_error", path=target_path, error=str(e))
            return jsonify({"code": 500, "message": f"Error writing to file: {path}"}), 500

    return jsonify({"ok": True})

@app.post("/api/rag/search")
def api_rag_search():
    body = request.get_json(silent=True) or {}
    q = body.get("q","")
    try:
        k = int(body.get("k",3))
        hops = int(body.get("hops",1))
        expansion_k = int(body.get("expansion_k",2))
    except (ValueError, TypeError):
        return jsonify({"code": 400, "message": "Parameters 'k', 'hops', and 'expansion_k' must be integers."}), 400
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

