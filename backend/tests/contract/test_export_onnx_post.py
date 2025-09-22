from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_export_onnx_contract():
    r = client.post("/api/export/onnx", json={"experimentId": "e1", "dynamicAxes": True})
    assert r.status_code == 202
