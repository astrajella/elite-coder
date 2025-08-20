
import asyncio
import pytest
from services.orchestrator.validation_wrapper import wrap_tool_call

async def async_bad_tool():
    # returns payload that does NOT conform to CodePatchList (missing patches as list)
    return {"plan_id":"p1","step_id":"s1","patches":"this-should-be-a-list"}

@pytest.mark.asyncio
async def test_validation_failure_and_retry(monkeypatch):
    # wrap the bad tool and expect validation to mark it invalid
    result = await wrap_tool_call("tool_generate_code", "coder", async_bad_tool, expected_schema="CodePatchList", correlation_id="c1", run_id="r1")
    assert "_validation" in result
    assert result["_validation"]["valid"] == False
