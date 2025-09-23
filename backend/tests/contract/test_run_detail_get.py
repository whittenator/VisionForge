from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_run_detail_contract():
    r = client.get("/api/experiments/runs/demo-run")
    assert r.status_code in (200, 404)
