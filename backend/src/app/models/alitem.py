from __future__ import annotations

import uuid

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ALItem(Base):
    __tablename__ = "al_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    al_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("al_runs.id"), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"), nullable=False)
    priority: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    proposed_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    resolved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
