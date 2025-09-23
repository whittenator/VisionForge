import os
import sys
from fastapi.testclient import TestClient

CURRENT_DIR = os.path.dirname(__file__)
SRC_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "src"))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from app.main import app

client = TestClient(app)

def test_login_invalid_returns_401():
    r = client.post("/auth/login", json={"email": "nobody@example.com", "password": "bad"})
    assert r.status_code == 401
