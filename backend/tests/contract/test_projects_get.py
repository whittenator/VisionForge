import os
import sys
from fastapi.testclient import TestClient

CURRENT_DIR = os.path.dirname(__file__)
SRC_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "src"))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from app.main import app

client = TestClient(app)


def test_list_projects_contract_returns_array():
    r = client.get("/api/projects")
    assert r.status_code in (200, 204)
    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, list)
