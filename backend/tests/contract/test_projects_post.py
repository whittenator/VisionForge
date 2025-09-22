from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_create_project_contract():
    payload = {"name": "Demo", "description": "Test"}
    r = client.post("/api/projects", json=payload)
    assert r.status_code == 201
    assert "id" in r.json()
