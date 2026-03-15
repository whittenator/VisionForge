"""Unit tests for auth service — bcrypt hashing and JWT token functions."""
from __future__ import annotations

import pytest
from app.services import auth


def test_hash_password_produces_bcrypt_hash():
    """Password hash should start with $2b$ (bcrypt prefix)."""
    hashed = auth._hash_password("password123")
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")


def test_verify_password_correct():
    raw = "correct-horse-battery-staple"
    hashed = auth._hash_password(raw)
    assert auth._verify_password(raw, hashed) is True


def test_verify_password_wrong():
    hashed = auth._hash_password("right")
    assert auth._verify_password("wrong", hashed) is False


def test_create_access_token_is_string():
    token = auth.create_access_token("user-123", "test@example.com")
    assert isinstance(token, str)
    assert len(token) > 20


def test_decode_access_token_roundtrip():
    user_id = "abc-123"
    email = "me@example.com"
    token = auth.create_access_token(user_id, email)
    payload = auth.decode_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["email"] == email
    assert payload.get("type") == "access"


def test_decode_refresh_token_roundtrip():
    token = auth.create_refresh_token("user-456")
    payload = auth.decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-456"
    assert payload.get("type") == "refresh"


def test_decode_invalid_token_returns_none():
    assert auth.decode_token("not.a.valid.token") is None
    assert auth.decode_token("") is None


def test_authenticate_rejects_invalid_credentials():
    """authenticate() should return None for an unknown user."""
    result = auth.authenticate("nonexistent@example.com", "anypassword")
    assert result is None
