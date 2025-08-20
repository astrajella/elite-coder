from services.common.validation import enforce_and_apply
from services.common.schemas import CodePatchList

def fake_apply(payload):
    # simulate apply returning ok
    return {'applied': True, 'count': len(payload.get('patches', []))}

def test_enforce_and_apply_success():
    payload = {'plan_id':'p1','step_id':'s1','patches':[{'path':'a','type':'create','content':'x'}]}
    res = enforce_and_apply(CodePatchList, payload, fake_apply)
    assert res['applied'] is True

def test_enforce_and_apply_fail():
    payload = {'plan_id':'p1'}  # missing fields
    try:
        enforce_and_apply(CodePatchList, payload, fake_apply)
        assert False, "should have raised"
    except ValueError as e:
        assert 'validation_failed' in str(e)
