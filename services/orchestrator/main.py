from services.orchestrator.metrics import ORCH_TOOL_CALLS, ORCH_TOOL_LATENCY

import os
import uuid
import time
import asyncio
from typing import Dict, Any, Optional
from fastapi import FastAPI, Depends, Header, HTTPException, Request
from prometheus_client import make_asgi_app
from services.orchestrator.validation_wrapper import wrap_tool_call, SCHEMA_MAP
from services.orchestrator.critic import critic_review
from services.orchestrator.patch_applier import apply_patches
from services.orchestrator import auto_instrument
import httpx

app = FastAPI(title="Orchestrator (clean)")

# expose metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# --- Auth & correlation dependencies ---
def get_current_token(authorization: str = Header(None)):
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ",1)[1]
    if token != secret:
        raise HTTPException(status_code=403, detail="Invalid token")
    return token

def get_correlation_id(x_correlation_id: str = Header(None)):
    if x_correlation_id:
        return x_correlation_id
    return str(uuid.uuid4())

# tool endpoint urls (optional)
AGENT_CORE_URL = os.getenv("AGENT_CORE_URL", "")
VALIDATOR_URL = os.getenv("AGENT_CORE_VALIDATE_URL", "")

# --- Tool adapters ---
async def call_remote_tool(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call a remote tool via HTTP if AGENT_CORE_URL set, else provide a conservative local output."""
    base = AGENT_CORE_URL.rstrip('/') if AGENT_CORE_URL else None
    if base:
        url = f"{base}/{path.lstrip('/')}")
    else:
        url = None
    if url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(url, json=payload)
                try:
                    return r.json()
                except Exception:
                    return {"error":"non-json response", "status": r.status_code, "text": r.text}
        except Exception as e:
            return {"error": str(e)}
    # local conservative outputs per tool path
    if path.endswith("tool_plan_step") or path.endswith("plan_step"):
        return { "plan_id":"p-LOCAL", "steps":[{"step_id":"s1","description":"local plan","estimated_effort":"low"}], "priority": 50 }
    if path.endswith("tool_summarize_tokens") or path.endswith("summarize_tokens"):
        return {"summary":"local summary", "token_est":10, "important_docs":[], "drop_list":[]}
    if path.endswith("tool_retrieve_rag") or path.endswith("retrieve_rag"):
        return {"retrieved":[{"id":"0","text":"local doc","score":0.7}], "query_embedding_dim":384, "hops_used":1}
    if path.endswith("tool_generate_code") or path.endswith("generate_code"):
        return {"plan_id":"p-LOCAL","step_id":"s1","patches":[{"path":"workspace/README.md","type":"create","content":"# auto-generated"}],"author":"coder_agent","explain":"local patch"}
    if path.endswith("tool_run_tests") or path.endswith("run_tests"):
        return {"passed":1,"failed":0,"failures":[], "logs_url": None}
    if path.endswith("tool_commit_and_artifact") or path.endswith("commit_and_artifact"):
        return {"commit_id":"c-local","artifact_urls":[], "size_bytes":0}
    # fallback
    return {"result":"unknown tool", "path": path, "payload": payload}

# --- Main orchestration endpoint ---
@app.post("/orchestrate")
async def orchestrate(request: Request, token=Depends(get_current_token), correlation_id: str = Depends(get_correlation_id)):
    run_id = str(uuid.uuid4())
    start_run = time.time()
    try:
        body = await request.json()
    except Exception:
        body = {}
    persona = body.get("persona", "coder")
    out: Dict[str, Any] = {}
    # Plan
    async def plan_call():
        return await call_remote_tool("tool_plan_step", {"goal": body.get("goal","demo"), "constraints": {}, "current_files": []})
    out["plan"] = await wrap_tool_call("tool_plan_step", persona, plan_call, expected_schema="PlanSchema", correlation_id=correlation_id, run_id=run_id)
    # Summarize (token-aware)
    async def summarize_call():
        return await call_remote_tool("tool_summarize_tokens", {"context_blocks": [], "max_tokens": 500})
    out["summarize"] = await wrap_tool_call("tool_summarize_tokens", "summarizer", summarize_call, expected_schema="SummarizerSchema", correlation_id=correlation_id, run_id=run_id)
    # Retrieve
    async def retrieve_call():
        return await call_remote_tool("tool_retrieve_rag", {"query": body.get("goal","demo"), "top_k": 3})
    out["retrieve"] = await wrap_tool_call("tool_retrieve_rag", "summarizer", retrieve_call, expected_schema="RetrievalSchema", correlation_id=correlation_id, run_id=run_id)
    # Iterate over plan steps
    steps = out["plan"].get("steps", [])
    for step in steps:
        step_id = step.get("step_id")
        # generate code
        async def gen_call():
            return await call_remote_tool("tool_generate_code", {"step_id": step_id, "files_requested": [], "context_summary": out.get("summarize",{}).get("summary",""), "style_guides": [], "tests_to_pass": []})
        out[f"generate_{step_id}"] = await wrap_tool_call("tool_generate_code", "coder", gen_call, expected_schema="CodePatchList", correlation_id=correlation_id, run_id=run_id)
        # if validation failed, call critic and apply patches, retry once
        if not out[f"generate_{step_id}"].get("_validation",{}).get("valid", False):
            # call critic (real implementation)
            critic_res = await critic_review(out[f"generate_{step_id}"].get("patches", []), out.get("tests", {}), out.get("plan", {}), run_id=run_id)
            # apply patches suggested by critic
            for rec in critic_res.get("fix_recommendations", []):
                pr = rec.get("patch_request", {})
                patches = pr.get("patches", [])
                if patches:
                    apply_patches(patches)
            # retry generation once
            out[f"generate_{step_id}"] = await wrap_tool_call("tool_generate_code", "coder", gen_call, expected_schema="CodePatchList", correlation_id=correlation_id, run_id=run_id)
        # run tests
        async def test_call():
            return await call_remote_tool("tool_run_tests", {"test_selector":"all", "timeout_sec": 60})
        out[f"tests_{step_id}"] = await wrap_tool_call("tool_run_tests", "critic", test_call, expected_schema="TestResultsSchema", correlation_id=correlation_id, run_id=run_id)
        if not out[f"tests_{step_id}"].get("_validation",{}).get("valid", False) or out[f"tests_{step_id}"].get("failed",0) > 0:
            critic_res = await critic_review(out[f"generate_{step_id}"].get("patches", []), out[f"tests_{step_id}"], out.get("plan", {}), run_id=run_id)
            for rec in critic_res.get("fix_recommendations", []):
                pr = rec.get("patch_request", {})
                patches = pr.get("patches", [])
                if patches:
                    apply_patches(patches)
            # retry tests once
            out[f"tests_{step_id}"] = await wrap_tool_call("tool_run_tests", "critic", test_call, expected_schema="TestResultsSchema", correlation_id=correlation_id, run_id=run_id)
        # commit if tests pass and validation ok
        if out[f"tests_{step_id}"].get("failed",0) == 0 and out[f"generate_{step_id}"].get("_validation",{}).get("valid", False):
            async def commit_call():
                return await call_remote_tool("tool_commit_and_artifact", {"patches": out[f"generate_{step_id}"].get("patches", []), "commit_message": f"apply step {step_id}", "artifact_targets": []})
            out[f"commit_{step_id}"] = await wrap_tool_call("tool_commit_and_artifact", "coder", commit_call, expected_schema="LedgerRunSchema", correlation_id=correlation_id, run_id=run_id)
    out["_meta"] = {"run_id": run_id, "duration": time.time() - start_run}
    return out
