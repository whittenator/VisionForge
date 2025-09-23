from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_login_invalid_returns_401():
    r = client.post("/auth/login", json={"email": "nobody@example.com", "password": "bad"})
    assert r.status_code == 401
