"""Registry mapping framework keys to :class:`Trainer` instances.

Built-in trainers register themselves at import time (see the package
``__init__``). New libraries are added by implementing :class:`Trainer` and
calling :func:`register` — no edits to the Celery tasks, services, or frontend.
"""

from __future__ import annotations

from app.services.training.base import Trainer

# The default framework for runs/artifacts created before frameworks existed,
# and whenever a caller omits the framework.
DEFAULT_FRAMEWORK = "ultralytics"

_REGISTRY: dict[str, Trainer] = {}


class UnknownFrameworkError(Exception):
    """Raised when a framework key has no registered trainer."""


def register(trainer: Trainer) -> Trainer:
    """Register a trainer instance under its ``key``. Idempotent (last wins)."""
    if not trainer.key:
        raise ValueError("Trainer.key must be a non-empty string")
    _REGISTRY[trainer.key] = trainer
    return trainer


def get_trainer(key: str | None) -> Trainer:
    """Resolve a trainer by key, defaulting to Ultralytics for back-compat.

    A ``None``/empty key maps to :data:`DEFAULT_FRAMEWORK` so existing runs and
    artifacts (which predate the ``framework`` column) keep working unchanged.
    """
    resolved = (key or DEFAULT_FRAMEWORK).strip() or DEFAULT_FRAMEWORK
    trainer = _REGISTRY.get(resolved)
    if trainer is None:
        raise UnknownFrameworkError(f"no trainer registered for framework {resolved!r}")
    return trainer


def list_frameworks() -> list[Trainer]:
    """Return all registered trainers (stable order by key)."""
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def is_registered(key: str | None) -> bool:
    return bool(key) and key in _REGISTRY
