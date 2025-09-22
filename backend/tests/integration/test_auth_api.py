from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_login_success_and_logout():
    r = client.post("/auth/login", json={"email": "demo@example.com", "password": "password123"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("token")
    assert data.get("user", {}).get("email") == "demo@example.com"

    r2 = client.post("/auth/logout")
    assert r2.status_code == 204


def test_login_invalid_returns_401():
    r = client.post("/auth/login", json={"email": "nope@example.com", "password": "wrong"})
    assert r.status_code == 401
