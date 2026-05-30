"""Pluggable training-backend abstraction.

VisionForge supports more than one training library (Ultralytics/YOLO for
detection-family tasks, Timm for image classification, and — by design — others
in the future). Rather than hard-coding library names throughout the Celery
tasks, evaluation, and inference code, each library is wrapped in a ``Trainer``
implementation (see ``base.py``) and registered in ``registry.py``. Orchestration
code resolves the right trainer by its ``key`` and delegates.

Importing this package registers the built-in trainers as a side effect, so
``from app.services import training`` is enough to populate the registry.
"""

from __future__ import annotations

from app.services.training.base import (
    Capabilities,
    FieldDef,
    FieldGroup,
    TrainContext,
    Trainer,
    TrainResult,
)
from app.services.training.registry import get_trainer, list_frameworks, register

# Register built-in trainers. Each import self-registers via ``register(...)``.
# Wrapped defensively so a missing optional dependency at import time never
# prevents the rest of the app from starting.
try:  # pragma: no cover - exercised indirectly
    from app.services.training import ultralytics_trainer  # noqa: F401
except Exception:  # pragma: no cover
    pass

try:  # pragma: no cover - exercised indirectly
    from app.services.training import timm_trainer  # noqa: F401
except Exception:  # pragma: no cover
    pass

__all__ = [
    "Capabilities",
    "FieldDef",
    "FieldGroup",
    "Trainer",
    "TrainContext",
    "TrainResult",
    "get_trainer",
    "list_frameworks",
    "register",
]
