from __future__ import annotations

import uuid

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_login_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active_devices: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # JSON string or similar
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
