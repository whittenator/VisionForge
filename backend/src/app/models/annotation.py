from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # box, polygon, etc.
    geometry: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    class_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    history: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
