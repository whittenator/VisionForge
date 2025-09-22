from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_ingest_flow_e2e():
    # Create project
    r = client.post("/api/projects", json={"name": "E2E", "description": "flow"})
    assert r.status_code == 201
    proj = r.json()

    # Create dataset under project
    r = client.post(f"/api/datasets/{proj['id']}", json={"name": "ds", "media_type": "image"})
    assert r.status_code == 201
    ds = r.json()

    # Request upload URL for dataset version
    r = client.post(
        "/api/ingest/upload-url",
        json={"datasetVersionId": ds["activeVersionId"], "filename": "a.jpg", "contentType": "image/jpeg"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "url" in body and "fields" in body
