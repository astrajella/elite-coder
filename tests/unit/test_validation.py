from services.common.validation import validate_payload
from services.common.schemas import CodePatchList, FilePatch

def test_valid_codepatchlist():
    payload = {
        "plan_id":"p1",
        "step_id":"s1",
        "patches":[{"path":"a.txt","type":"create","content":"hello"}],
        "author":"coder_agent"
    }
    res = validate_payload(CodePatchList, payload)
    assert res.valid is True
    assert res.payload is not None

def test_invalid_codepatchlist_missing_fields():
    payload = {"plan_id":"p1"}
    res = validate_payload(CodePatchList, payload)
    assert res.valid is False
    assert isinstance(res.errors, list)
