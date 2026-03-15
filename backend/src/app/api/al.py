from __future__ import annotations

import json
import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.alitem import ALItem
from app.models.alrun import ALRun
from app.models.asset import Asset
from app.models.user import User
from app.services.active_learning_service import select_diverse, select_uncertain
from app.services.embeddings_service import EmbeddingsService

router = APIRouter(prefix="/api/al", tags=["active-learning"])


class ALSelectRequest(BaseModel):
    dataset_version_id: str
    project_id: str
    strategy: str = "uncertainty"  # "uncertainty" or "diverse"
    k: int = 20  # number of samples to select
    model_id: str | None = None  # for uncertainty scoring


@router.post("/select", status_code=201)
def select_samples(
    body: ALSelectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get unlabeled assets for this version
    assets = list(
        db.scalars(
            select(Asset).where(
                Asset.version_id == body.dataset_version_id,
                Asset.label_status.in_(["unlabeled", "unlabelled", "in_progress"]),
            )
        ).all()
    )

    if not assets:
        return {"selected_asset_ids": [], "strategy": body.strategy, "count": 0}

    k = min(body.k, len(assets))

    if body.strategy == "diverse":
        # Use embeddings for diversity sampling
        svc = EmbeddingsService()
        embeddings: list[list[float]] = []
        for a in assets:
            meta: dict = {}
            try:
                meta = json.loads(a.meta_data or "{}")
            except Exception:
                pass
            emb = meta.get("embedding")
            if emb and isinstance(emb, list):
                embeddings.append(emb)
            else:
                embeddings.append(svc.embed_texts([a.uri])[0])
        indices = select_diverse(embeddings, k)
    else:
        # Default: random uncertainty scores (no model available at select time)
        scores = [random.random() for _ in assets]
        indices = select_uncertain(scores, k)

    selected = [assets[i] for i in indices if i < len(assets)]

    # Create ALRun and ALItems (ALRun has: project_id, strategy, params_json)
    al_run = ALRun(
        project_id=body.project_id,
        strategy=body.strategy,
        params_json=json.dumps({"dataset_version_id": body.dataset_version_id, "k": k}),
    )
    db.add(al_run)
    db.flush()

    for i, asset in enumerate(selected):
        priority = float(len(selected) - i) / len(selected)  # descending priority
        item = ALItem(
            al_run_id=al_run.id,
            asset_id=asset.id,
            priority=priority,
            resolved_status="pending",
        )
        db.add(item)
    db.commit()

    return {
        "al_run_id": al_run.id,
        "selected_asset_ids": [a.id for a in selected],
        "strategy": body.strategy,
        "count": len(selected),
    }


@router.get("/runs")
def list_runs(
    project_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(ALRun)
    if project_id:
        q = q.where(ALRun.project_id == project_id)
    runs = list(db.scalars(q).all())
    return [
        {
            "id": r.id,
            "project_id": r.project_id,
            "strategy": r.strategy,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]


@router.get("/runs/{al_run_id}/items")
def get_al_items(
    al_run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = list(db.scalars(select(ALItem).where(ALItem.al_run_id == al_run_id)).all())
    return [
        {
            "id": i.id,
            "asset_id": i.asset_id,
            "priority": i.priority,
            "resolved_status": i.resolved_status,
        }
        for i in items
    ]


@router.put("/runs/{al_run_id}/items/{item_id}/resolve")
def resolve_item(
    al_run_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(ALItem, item_id)
    if not item or item.al_run_id != al_run_id:
        raise HTTPException(status_code=404, detail="AL item not found")
    item.resolved_status = "resolved"
    item.resolved_by = current_user.id
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "asset_id": item.asset_id,
        "priority": item.priority,
        "resolved_status": item.resolved_status,
    }
