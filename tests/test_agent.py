import requests, os, time
import pytest
BASE = os.getenv('AGENT_URL','http://127.0.0.1:8001')

@pytest.mark.skip(reason="Integration test that requires a running agent-core service")
def test_invoke_tool():
    # Use simple dev token as Bearer
    headers = {'Authorization': 'Bearer ' + os.getenv('JWT_SECRET','devsecret')}
    r = requests.post(f'{BASE}/invoke_tool', json={'tool':'generate_code','payload':{}}, headers=headers)
    assert r.status_code == 200
