from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_login_invalid_credentials_returns_401():
    r = client.post("/auth/login", json={"email": "nope@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_logout_returns_204_even_if_not_logged_in():
    r = client.post("/auth/logout")
    assert r.status_code == 204


def test_login_valid_credentials_returns_token_and_user():
    # NOTE: This assumes MVP credentials documented in research.md are accepted
    payload = {"email": "demo@example.com", "password": "password123"}
    r = client.post("/auth/login", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "token" in data and isinstance(data["token"], str) and data["token"]
    assert "user" in data and isinstance(data["user"], dict)
    assert data["user"].get("email") == payload["email"]
