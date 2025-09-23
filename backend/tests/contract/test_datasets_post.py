from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_create_dataset_contract():
    r = client.post("/api/datasets/demo-project", json={"name": "set"})
    assert r.status_code == 201
