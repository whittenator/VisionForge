from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_train_contract():
    r = client.post(
        "/api/train",
        json={"projectId": "p1", "datasetVersionId": "v1", "task": "classification", "params": {}},
    )
    assert r.status_code == 202
