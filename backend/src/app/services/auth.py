from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, TypedDict

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.models.workspace import Workspace

SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthUser(TypedDict):
    id: str
    email: str
    displayName: str


class EmailAlreadyExistsError(Exception):
    pass


def _hash_password(raw: str) -> str:
    return _pwd_context.hash(raw)


def _verify_password(raw: str, hashed: str) -> bool:
    return _pwd_context.verify(raw, hashed)


def _is_bcrypt_hash(hashed: str) -> bool:
    """Return True if the stored hash looks like a bcrypt hash."""
    return hashed.startswith(("$2b$", "$2a$", "$2y$"))


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(tz=timezone.utc) + (
        expires_delta if expires_delta is not None else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    to_encode["type"] = "access"
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(tz=timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode["exp"] = expire
    to_encode["type"] = "refresh"
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_from_token(token: str, db: Session) -> User:
    payload = decode_token(token)
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


def register(db: Session, *, name: str, email: str, password: str) -> User:
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise EmailAlreadyExistsError()
    u = User(email=email, name=name, password_hash=_hash_password(password))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def authenticate(email: str, password: str) -> Optional[tuple[str, str, AuthUser]]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if not user or not user.password_hash:
            return None

        # Support legacy SHA256 hashes during migration: verify by comparison,
        # then re-hash with bcrypt on successful login.
        if _is_bcrypt_hash(user.password_hash):
            if not _verify_password(password, user.password_hash):
                return None
        else:
            # Legacy SHA256 path
            import hashlib

            legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
            if user.password_hash != legacy_hash:
                return None
            # Upgrade to bcrypt in-place
            user.password_hash = _hash_password(password)
            db.add(user)
            db.commit()

        auth_user: AuthUser = {
            "id": user.id,
            "email": user.email,
            "displayName": user.name or user.email,
        }
        access_token = create_access_token({"sub": user.id})
        refresh_token = create_refresh_token({"sub": user.id})
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
