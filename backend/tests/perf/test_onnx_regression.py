import time

from tests.conftest import client


def test_onnx_export_job_succeeds_quickly():
    r = client.post("/api/export/onnx", json={"experimentId": "e1", "dynamicAxes": True})
    assert r.status_code == 202
    job = r.json()
    job_id = job["id"]

    # Poll job status (the task simulates success quickly)
    deadline = time.time() + 2.0
    status = None
    while time.time() < deadline:
        s = client.get(f"/api/jobs/{job_id}")
        assert s.status_code == 200
        status = s.json()["status"]
        if status in ("succeeded", "failed"):
            break
        time.sleep(0.05)

    assert status == "succeeded"
