
import os, time, json, asyncio
from typing import Optional, Dict, Any
import httpx
from pydantic import ValidationError
from services.common.schemas import CodePatchList, PlanSchema, TestResultsSchema, SummarizerSchema, ErrorResponse

SCHEMA_MAP = {
    "CodePatchList": CodePatchList,
    "PlanSchema": PlanSchema,
    "TestResultsSchema": TestResultsSchema,
    "SummarizerSchema": SummarizerSchema,
    "ErrorResponse": ErrorResponse,
}

AGENT_CORE_VALIDATE_URL = os.getenv("AGENT_CORE_VALIDATE_URL") or (
    (os.getenv("AGENT_CORE_URL") or "").rstrip("/") + "/tool_validate_schema"
)

async def validate_payload(expected_schema: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not expected_schema:
        return {"valid": False, "errors": [{"msg":"missing expected_schema"}]}
    model = SCHEMA_MAP.get(expected_schema)
    if model is None:
        return {"valid": False, "errors": [{"msg": f"unknown schema {expected_schema}"}]}
    try:
        model(**payload)
        local_ok = {"valid": True, "errors": []}
    except ValidationError as ve:
        local_ok = {"valid": False, "errors": [{"msg": e["msg"], "loc": e["loc"]} for e in ve.errors()]}

    # Prefer remote validator if available
    if AGENT_CORE_VALIDATE_URL and AGENT_CORE_VALIDATE_URL.startswith("http"):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(AGENT_CORE_VALIDATE_URL, json={"schema_name": expected_schema, "payload": payload})
                if r.status_code == 200:
                    return r.json()
        except Exception:
            pass  # fall back to local result
    return local_ok

async def wrap_tool_call(session: httpx.AsyncClient, url: str, json_payload: Dict[str, Any], expected_schema: Optional[str]=None, labels: Optional[Dict[str,str]]=None) -> Dict[str, Any]:
    labels = labels or {}
    persona = json_payload.get("persona") or labels.get("persona") or "unknown"
    tool = labels.get("tool") or (url.split("/")[-1] if url else "unknown")
    t0 = time.perf_counter()
    status = "error"
    try:
        resp = await session.post(url, json=json_payload)
        data = resp.json() if resp.headers.get("content-type","").startswith("application/json") else {"raw": resp.text}
        if not resp.is_success:
            status = "failure"
            result = {"error":"remote-failure", "status_code": resp.status_code, "data": data}
        else:
            # Schema check if expected
            if expected_schema:
                v = await validate_payload(expected_schema, data)
                if not v.get("valid"):
                    status = "failure"
                    result = {"error":"schema-validation-failed", "validator": v, "data": data}
                else:
                    status = "success"
                    result = data
            else:
                status = "success"
                result = data
    except Exception as e:
        result = {"error":"exception", "message": str(e)}
        status = "error"
    finally:
        dt = time.perf_counter() - t0
        try:
            # lazy import to avoid hard dep during unit tests
            from services.orchestrator.metrics import ORCH_TOOL_CALLS, ORCH_TOOL_LATENCY
            ORCH_TOOL_CALLS.labels(persona=persona, tool=tool, status=status).inc()
            ORCH_TOOL_LATENCY.labels(tool=tool).observe(dt)
        except Exception:
            pass
    return result
