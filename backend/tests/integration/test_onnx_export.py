from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_onnx_export_flow_e2e():
    # Request ONNX export
    r = client.post("/api/export/onnx", json={"experimentId": "e1", "dynamicAxes": True})
    assert r.status_code == 202
    body = r.json()
    assert "jobId" in body
