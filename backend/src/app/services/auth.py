from __future__ import annotations

import hashlib
import os
from typing import Optional, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User


class AuthUser(TypedDict):
  id: str
  email: str
  displayName: str


def _hash_password(raw: str) -> str:
  # MVP insecure hash; replace with bcrypt/argon2 in production
  return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class EmailAlreadyExistsError(Exception):
  pass


def register(db: Session, *, name: str, email: str, password: str) -> User:
  existing = db.scalar(select(User).where(User.email == email))
  if existing:
    raise EmailAlreadyExistsError()
  u = User(email=email, name=name, role="viewer", password_hash=_hash_password(password))
  db.add(u)
  db.commit()
  db.refresh(u)
  return u


def authenticate(email: str, password: str) -> Optional[tuple[str, AuthUser]]:
  with SessionLocal() as db:
    db = db  # type: Session
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.password_hash:
      return None
    if user.password_hash != _hash_password(password):
      return None
    token = f"token-{user.id}"
    return token, {"id": user.id, "email": user.email, "displayName": user.name or user.email}


def ensure_superuser() -> None:
  email = os.getenv("SUPERUSER_EMAIL")
  password = os.getenv("SUPERUSER_PASSWORD")
  if not email or not password:
    return
  with SessionLocal() as db:
    db = db  # type: Session
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
      # Update password if different
      hashed = _hash_password(password)
      if not existing.password_hash or existing.password_hash != hashed:
        existing.password_hash = hashed
        existing.role = existing.role or "admin"
        db.add(existing)
        db.commit()
      return
    u = User(email=email, name="Administrator", role="admin", password_hash=_hash_password(password))
    db.add(u)
    db.commit()
