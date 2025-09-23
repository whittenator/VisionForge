import time

from tests.conftest import client  # reuse TestClient

ROUTES = [
    ("/api/projects", {"name": "Perf", "description": "test"}),
    (
        "/api/ingest/upload-url",
        {
            "projectId": "p1",
            "fileName": "x.bin",
            "contentType": "application/octet-stream",
        },
    ),
]

def p95(latencies):
    latencies = sorted(latencies)
    idx = int(len(latencies) * 0.95) - 1
    idx = max(0, min(idx, len(latencies)-1))
    return latencies[idx]

def test_core_api_p95_under_200ms():
    latencies = []
    for path, payload in ROUTES:
        # warmup
        client.post(path, json=payload)
        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            r = client.post(path, json=payload)
            t1 = time.perf_counter()
            assert r.status_code in (200, 201, 202)
            times.append((t1 - t0) * 1000.0)
        latencies.extend(times)

    assert p95(latencies) < 200.0, f"p95 too high: {p95(latencies):.2f}ms"
