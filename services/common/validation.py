
import os, json, urllib.request
from typing import Dict, Any

AGENT_CORE_URL = os.getenv("AGENT_CORE_VALIDATE_URL") or os.getenv("AGENT_CORE_URL") or "http://localhost:8000"

def post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def validate_payload(schema_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{AGENT_CORE_URL}/tool_validate_schema"
    try:
        result = post_json(url, {"schema_name": schema_name, "payload": payload})
        if not result.get("valid", False):
            return {"valid": False, "errors": result.get("errors", [])}
        return {"valid": True, "errors": []}
    except Exception as e:
        return {"valid": False, "errors": [{"loc":["request"], "msg": str(e), "type":"request_error"}]}
