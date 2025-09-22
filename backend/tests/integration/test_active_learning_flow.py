from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_active_learning_flow_minimal():
    # Create project & dataset
    r = client.post("/api/projects", json={"name": "AL", "description": "flow"})
    assert r.status_code == 201
    proj = r.json()
    r = client.post(f"/api/datasets/{proj['id']}", json={"name": "ds", "media_type": "image"})
    assert r.status_code == 201

    # Trigger AL selection (placeholder contract)
    # This endpoint will be defined later; here we just assert 202 for placeholder
    r = client.post("/api/al/select", json={"projectId": proj["id"], "k": 5})
    assert r.status_code == 202
