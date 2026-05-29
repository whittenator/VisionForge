from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import TypedDict

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.models.workspace import Workspace

SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-32-chars-min")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# bcrypt work factor. 12 rounds is a sensible production default.
_BCRYPT_ROUNDS = 12
# bcrypt only considers the first 72 bytes of the input; longer passwords must be
# truncated explicitly or modern bcrypt (>=4.1) raises ValueError.
_BCRYPT_MAX_BYTES = 72


class AuthUser(TypedDict):
    id: str
    email: str
    displayName: str


class EmailAlreadyExistsError(Exception):
    pass


def _truncate(raw: str) -> bytes:
    """Encode and truncate to bcrypt's 72-byte limit."""
    return raw.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def _hash_password(raw: str) -> str:
    hashed = bcrypt.hashpw(_truncate(raw), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def _verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_truncate(raw), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _is_bcrypt_hash(hashed: str) -> bool:
    """Return True if the stored hash looks like a bcrypt hash."""
    return hashed.startswith(("$2b$", "$2a$", "$2y$"))


def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.now(tz=timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(tz=timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns the payload dict or None if invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user_from_token(token: str, db: Session) -> User:
    from fastapi import HTTPException, status

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def admin_reset_password(db: Session, user_id: str, new_password: str) -> User | None:
    """Admin-only password reset. Issues a fresh bcrypt hash."""
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        return None
    user.password_hash = _hash_password(new_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def register(db: Session, *, name: str, email: str, password: str) -> User:
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise EmailAlreadyExistsError()
    u = User(email=email, name=name, password_hash=_hash_password(password))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def authenticate(email: str, password: str) -> tuple[str, str, AuthUser] | None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if not user or not user.password_hash:
            return None

        # Bcrypt-only. Legacy SHA256 hashes are rejected and the user must
        # complete a password reset (via the password reset flow / admin tool).
        if not _is_bcrypt_hash(user.password_hash):
            return None
        if not _verify_password(password, user.password_hash):
            return None

        auth_user: AuthUser = {
            "id": user.id,
            "email": user.email,
            "displayName": user.name or user.email,
        }
        access_token = create_access_token(user.id, user.email)
        refresh_token = create_refresh_token(user.id)
        return access_token, refresh_token, auth_user


def ensure_superuser() -> None:
    email = os.getenv("FIRST_SUPERUSER_EMAIL") or os.getenv("SUPERUSER_EMAIL")
    password = os.getenv("FIRST_SUPERUSER_PASSWORD") or os.getenv("SUPERUSER_PASSWORD")
    if not email or not password:
        return

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            # Re-hash if the stored hash is not bcrypt
            if not existing.password_hash or not _is_bcrypt_hash(existing.password_hash):
                existing.password_hash = _hash_password(password)
                db.add(existing)
                db.commit()
            user = existing
        else:
            user = User(
                email=email,
                name="Administrator",
                password_hash=_hash_password(password),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Ensure default workspace exists
        default_workspace_id = "00000000-0000-0000-0000-000000000000"
        existing_workspace = db.scalar(
            select(Workspace).where(Workspace.id == default_workspace_id)
        )
        if not existing_workspace:
            workspace = Workspace(
                id=default_workspace_id,
                name="Default Workspace",
                created_by=user.id,
            )
            db.add(workspace)
            db.commit()
