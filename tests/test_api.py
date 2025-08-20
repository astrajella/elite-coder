from app import app
from services.schemas import CodePatchList, FilePatch, ErrorResponse

def test_commit_requires_schema():
    client = app.test_client()
    res = client.post('/tool_commit_and_artifact', json={"patches":[{"path":"x","type":"create","content":"x"}]})
    assert res.status_code == 400

def test_models_endpoint():
    client = app.test_client()
    res = client.get('/api/models')
    assert 'coder' in res.json and 'critic' in res.json and 'summarizer' in res.json
