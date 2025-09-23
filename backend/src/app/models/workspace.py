from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Role(str, Enum):
    VIEWER = "viewer"
    ANNOTATOR = "annotator"
    DEVELOPER = "developer"
    ADMIN = "admin"
    OWNER = "owner"


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    region: Mapped[str] = mapped_column(String(10), nullable=False, default="US")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False)
    role: Mapped[Role] = mapped_column(String(32), nullable=False, default=Role.VIEWER)
    invited_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    invited_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)