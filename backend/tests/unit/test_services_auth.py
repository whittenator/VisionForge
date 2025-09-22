from app.services import auth


def test_authenticate_accepts_demo_credentials():
    result = auth.authenticate("demo@example.com", "password123")
    assert result is not None
    token, user = result
    assert token
    assert user["email"] == "demo@example.com"


def test_authenticate_rejects_invalid_credentials():
    assert auth.authenticate("nope@example.com", "wrong") is None
