"""Training capabilities API.

Exposes the registered training backends and their form schemas so the frontend
can render each framework's training form dynamically — no library-specific UI
code. Also provides a model-search endpoint for backends with large catalogues
(e.g. Timm's ~1300 architectures).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.deps import get_current_user
from app.models.user import User
from app.services import training as training_pkg

router = APIRouter(prefix="/api/training", tags=["training"])


@router.get("/frameworks")
def list_frameworks(current_user: User = Depends(get_current_user)) -> dict:
    """Return every registered training backend with its capability descriptor."""
    return {"items": [t.capabilities().to_dict() for t in training_pkg.list_frameworks()]}


@router.get("/frameworks/{key}/models")
def search_models(
    key: str,
    task: str = Query("classify"),
    query: str = Query("", alias="query"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Search a framework's model catalogue (powers the searchable backbone picker)."""
    try:
        trainer = training_pkg.get_trainer(key)
    except training_pkg.registry.UnknownFrameworkError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"items": trainer.list_models(task, query)}
