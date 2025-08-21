from services.common.validation import validate_payload
from services.common.schemas import CodePatchList, FilePatch
import pytest

def test_valid_codepatchlist(monkeypatch):
    # Mock the underlying post_json call to avoid a real HTTP request
    def mock_post_json(url, payload_data):
        return {"valid": True, "payload": payload_data["payload"]}

    monkeypatch.setattr("services.common.validation.post_json", mock_post_json)

    payload = {
        "plan_id":"p1",
        "step_id":"s1",
        "patches":[{"path":"a.txt","type":"create","content":"hello"}],
        "author":"coder_agent"
    }
    res = validate_payload(CodePatchList, payload)
    assert res["valid"] is True
    assert res["payload"] is not None

def test_invalid_codepatchlist_missing_fields(monkeypatch):
    # Mock the underlying post_json call to simulate a validation failure
    def mock_post_json(url, payload_data):
        return {"valid": False, "errors": ["Missing required field"]}

    monkeypatch.setattr("services.common.validation.post_json", mock_post_json)

    payload = {"plan_id":"p1"}
    res = validate_payload(CodePatchList, payload)
    assert res["valid"] is False
    assert isinstance(res["errors"], list)
