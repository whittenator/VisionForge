from __future__ import annotations

import json
import random

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.alitem import ALItem
from app.models.alrun import ALRun
from app.models.artifact import ModelArtifact
from app.models.asset import Asset
from app.models.user import User
from app.services import inference_service
from app.services.active_learning_service import select_diverse, select_uncertain
from app.services.embeddings_service import EmbeddingsService

router = APIRouter(prefix="/api/al", tags=["active-learning"])


def _uncertainty_scores(db: Session, assets: list, model_id: str | None) -> list[float]:
    """Compute uncertainty scores for ``assets`` using ``model_id`` if available.

    When a model artifact is provided we run actual inference and use a margin-
    based uncertainty proxy (``1 - top_score``). When no model is available the
    pre-trained bootstrap path returns a uniform random score, which is still a
    reasonable cold-start strategy.
    """
    if not model_id:
        return [random.random() for _ in assets]
    artifact = db.get(ModelArtifact, model_id)
    if artifact is None or not artifact.storage_path:
        return [random.random() for _ in assets]

    scores: list[float] = []
    for asset in assets:
        try:
            from urllib.request import urlopen

            if asset.uri.startswith(("http://", "https://")):
                with urlopen(asset.uri, timeout=10) as response:  # noqa: S310
                    image_bytes = response.read()
            elif asset.uri:
                # MinIO key
                from app.services import storage as _storage

                client = _storage.get_minio_client()
                import os as _os

                bucket = _os.getenv("MINIO_BUCKET", _os.getenv("S3_BUCKET", "visionforge"))
                resp = client.get_object(bucket, asset.uri)
                try:
                    image_bytes = resp.read()
                finally:
                    resp.close()
                    resp.release_conn()
            else:
                scores.append(random.random())
                continue
            result = inference_service.predict(artifact, image_bytes, score_threshold=0.0)
            top = _top_confidence(result)
            scores.append(1.0 - float(top))
        except Exception:
            # Fall back to a random score for this asset rather than dropping it.
            scores.append(random.random())
    return scores


def _top_confidence(result: dict | list) -> float:
    """Pick the most confident prediction's score from an inference result."""
    if isinstance(result, dict):
        cls_pred = result.get("classification")
        if isinstance(cls_pred, dict) and "score" in cls_pred:
            try:
                return float(cls_pred["score"])
            except Exception:
                pass
        if "top_score" in result:
            try:
                return float(result["top_score"])
            except Exception:
                pass
        boxes = result.get("detections") or result.get("predictions") or []
    elif isinstance(result, list):
        boxes = result
    else:
        boxes = []
    if not boxes:
        return 0.0
    best = 0.0
    for b in boxes:
        score = b.get("score") or b.get("confidence") or 0.0
        try:
            score = float(score)
        except Exception:
            continue
        if score > best:
            best = score
    return best


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
        scores = _uncertainty_scores(db, assets, body.model_id)
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
    project_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = select(ALRun)
    if project_id:
        base = base.where(ALRun.project_id == project_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    offset = (page - 1) * page_size
    runs = list(
        db.scalars(base.order_by(ALRun.created_at.desc()).offset(offset).limit(page_size)).all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "project_id": r.project_id,
                "strategy": r.strategy,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


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
