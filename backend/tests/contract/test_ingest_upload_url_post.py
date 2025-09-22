from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_ingest_upload_url_contract():
    r = client.post(
        "/api/ingest/upload-url",
        json={"datasetVersionId": "v1", "filename": "a.jpg", "contentType": "image/jpeg"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "url" in body
