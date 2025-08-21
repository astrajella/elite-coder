from app import app
from services.schemas import CodePatchList, FilePatch, ErrorResponse

def test_models_endpoint():
    client = app.test_client()
    res = client.get('/api/models')
    assert 'coder' in res.json and 'critic' in res.json and 'summarizer' in res.json
