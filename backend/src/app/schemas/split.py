from __future__ import annotations

from pydantic import BaseModel, Field


class SplitConfig(BaseModel):
    """Operator-supplied train/val/test split configuration."""

    train: float = Field(0.8, ge=0)
    val: float = Field(0.2, ge=0)
    test: float = Field(0.0, ge=0)
    seed: int = 42
    stratify: bool = True


class SplitCounts(BaseModel):
    train: int = 0
    val: int = 0
    test: int = 0
    unassigned: int = 0


class SplitSummary(BaseModel):
    total: int
    counts: SplitCounts
    per_class: dict[str, dict[str, int]] = {}
    ratios: dict[str, float] | None = None
    seed: int | None = None
    stratify: bool | None = None
