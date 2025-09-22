from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_training_flow_e2e():
    # Create project
    r = client.post("/api/projects", json={"name": "Train", "description": "flow"})
    assert r.status_code == 201
    proj = r.json()

    # Create dataset and kick off training
    r = client.post(f"/api/datasets/{proj['id']}", json={"name": "ds", "media_type": "image"})
    assert r.status_code == 201

    r = client.post(
        "/api/train",
        json={"projectId": proj["id"], "datasetVersionId": "v1", "task": "classification", "params": {}},
    )
    assert r.status_code == 202
    body = r.json()
    assert "jobId" in body
