from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_list_runs_contract():
    r = client.get("/api/experiments/runs")
    assert r.status_code in (200, 204)
