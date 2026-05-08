from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# Allowed annotation types. Keep in sync with the frontend toolbox.
ANNOTATION_TYPES = ("box", "polygon", "keypoint", "classification")


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    geometry: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    class_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    # Optimistic-lock counter. Bumped on every update; clients must send the
    # current version to apply changes.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # JSON array of {version, geometry, class_name, updated_at}
    history: Mapped[str | None] = mapped_column(Text, nullable=True)
