from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.alitem import ALItem
from app.models.alrun import ALRun
from app.models.artifact import ModelArtifact
from app.models.asset import Asset
from app.models.dataset_version import DatasetVersion
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Membership, Role
from app.services import authz, inference_service, training_service
from app.services.active_learning_service import (
    resolution_stats,
    select_diverse,
    select_uncertain,
)
from app.services.asset_fetch import fetch_asset_bytes
from app.services.embeddings_service import EmbeddingsService

router = APIRouter(prefix="/api/al", tags=["active-learning"])

# Hard cap on the number of assets scored inline by the API request. Larger
# pools fall back to random for the excess + can be scored fully via the
# `app.jobs.tasks.al_uncertainty.score_assets` Celery task. Tunable via env.
_INLINE_SCORE_CAP = int(os.getenv("VF_AL_INLINE_SCORE_CAP", "200"))


def _member_workspace_ids(db: Session, user: User) -> list[str]:
    ws_ids = {
        m.workspace_id
        for m in db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    }
    ws_ids.add(authz.DEFAULT_WORKSPACE_ID)
    return list(ws_ids)


def _uncertainty_scores(db: Session, assets: list, model_id: str | None) -> list[float]:
    """Compute uncertainty scores for ``assets`` using ``model_id`` if available.

    When a model artifact is provided we run actual inference on up to
    ``_INLINE_SCORE_CAP`` assets and use a margin-based uncertainty proxy
    (``1 - top_score``). Anything beyond the cap (or any inference failure)
    falls back to a random score so the request stays fast and never blocks
    indefinitely on heavy I/O. For full-pool scoring, dispatch
    ``app.jobs.tasks.al_uncertainty.score_assets`` as a background job — it
    persists per-asset scores into ``Asset.meta_data["uncertainty"]`` which
    this function will pick up on subsequent calls.
    """
    if not model_id:
        return [random.random() for _ in assets]
    artifact = db.get(ModelArtifact, model_id)
    if artifact is None or not artifact.storage_path:
        return [random.random() for _ in assets]

    scores: list[float] = []
    inline_budget = _INLINE_SCORE_CAP
    for asset in assets:
        # First try a cached score from a prior background job.
        cached = _cached_uncertainty(asset)
        if cached is not None:
            scores.append(cached)
            continue
        if inline_budget <= 0:
            # Exceeded the per-request cap — degrade to random rather than
            # hold up the API thread.
            scores.append(random.random())
            continue
        try:
            image_bytes = fetch_asset_bytes(asset.uri)
            if not image_bytes:
                scores.append(random.random())
                continue
            result = inference_service.predict(artifact, image_bytes, score_threshold=0.0)
            top = _top_confidence(result)
            scores.append(1.0 - float(top))
        except Exception:
            scores.append(random.random())
        inline_budget -= 1
    return scores


def _cached_uncertainty(asset) -> float | None:
    """Read a previously-computed uncertainty score from ``meta_data``."""
    md = getattr(asset, "meta_data", None)
    if not md:
        return None
    try:
        parsed = json.loads(md)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    val = parsed.get("uncertainty")
    if isinstance(val, (int, float)):
        return float(val)
    return None


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


class ALScoreRequest(BaseModel):
    dataset_version_id: str
    artifact_id: str
    max_assets: int = 0  # 0 = no cap


@router.post("/score", status_code=202)
def queue_uncertainty_scoring(
    body: ALScoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Queue a Celery job that pre-computes per-asset uncertainty scores.

    Use this for full-pool scoring on large datasets so `/api/al/select`
    can read cached scores instead of running inference inline.
    """
    from app.jobs.celery_app import celery_app
    from app.services.jobs_service import create_job, update_job_status

    artifact = db.get(ModelArtifact, body.artifact_id)
    if not artifact:
        raise HTTPException(status_code=400, detail="artifact not found")
    version = db.get(DatasetVersion, body.dataset_version_id)
    if not version:
        raise HTTPException(status_code=400, detail="dataset version not found")
    authz.require_project_access(db, current_user, artifact.project_id, Role.DEVELOPER)
    authz.require_dataset_access(db, current_user, version.dataset_id, Role.DEVELOPER)

    payload = {
        "artifactId": body.artifact_id,
        "datasetVersionId": body.dataset_version_id,
        "maxAssets": body.max_assets,
    }
    job = create_job(db, "al_uncertainty", payload)
    payload["jobId"] = job.id
    try:
        celery_app.send_task("app.jobs.tasks.al_uncertainty.score_assets", args=[payload])
    except Exception as exc:
        # Broker unavailable — surface failure rather than leaving the row queued.
        try:
            update_job_status(db, job.id, status="failed", progress=0.0)
        except Exception:
            pass
        raise HTTPException(status_code=503, detail=f"failed to dispatch task: {exc}") from exc
    return {"jobId": job.id, "status": "queued"}


@router.post("/select", status_code=201)
def select_samples(
    body: ALSelectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    authz.require_project_access(db, current_user, body.project_id, Role.DEVELOPER)
    version = db.get(DatasetVersion, body.dataset_version_id)
    if version is not None:
        authz.require_dataset_access(db, current_user, version.dataset_id, Role.DEVELOPER)
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
        authz.require_project_access(db, current_user, project_id, Role.VIEWER)
        base = base.where(ALRun.project_id == project_id)
    elif not authz.is_superuser(db, current_user):
        base = base.join(Project, ALRun.project_id == Project.id).where(
            Project.workspace_id.in_(_member_workspace_ids(db, current_user))
        )
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
    run = db.get(ALRun, al_run_id)
    if run is not None:
        authz.require_project_access(db, current_user, run.project_id, Role.VIEWER)
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
    run = db.get(ALRun, item.al_run_id)
    if run is not None:
        authz.require_project_access(db, current_user, run.project_id, Role.ANNOTATOR)
    item.resolved_status = "resolved"
    item.resolved_by = current_user.id
    item.resolved_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "asset_id": item.asset_id,
        "priority": item.priority,
        "resolved_status": item.resolved_status,
    }


class ALRetrainRequest(BaseModel):
    dataset_version_id: str | None = None
    task: str | None = None
    framework: str | None = None
    cluster_id: str | None = None
    base_model: str | None = None
    params: dict | None = None

    model_config = {
        "populate_by_name": True,
        "alias_generator": lambda name: "".join(
            w if i == 0 else w.capitalize() for i, w in enumerate(name.split("_"))
        ),
    }


def _run_dataset_version_id(run: ALRun) -> str | None:
    """Read the dataset version id the AL run was created against (if stored)."""
    if not run.params_json:
        return None
    try:
        params = json.loads(run.params_json)
    except Exception:
        return None
    if isinstance(params, dict):
        val = params.get("dataset_version_id")
        if isinstance(val, str) and val:
            return val
    return None


def _dataset_task_type(db: Session, dataset_version_id: str) -> str | None:
    """Resolve the dataset's task_type via a dataset version, if available."""
    from app.models.dataset import Dataset

    version = db.get(DatasetVersion, dataset_version_id)
    if version is None:
        return None
    dataset = db.get(Dataset, version.dataset_id)
    return getattr(dataset, "task_type", None) if dataset is not None else None


@router.get("/runs/{al_run_id}/progress")
def get_al_progress(
    al_run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.get(ALRun, al_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="AL run not found")
    authz.require_project_access(db, current_user, run.project_id, Role.VIEWER)
    stats = resolution_stats(db, al_run_id)
    return {
        "al_run_id": run.id,
        "total": stats["total"],
        "resolved": stats["resolved"],
        "pending": stats["pending"],
        "last_train_run_id": run.last_train_run_id,
    }


@router.post("/runs/{al_run_id}/retrain", status_code=201)
def retrain_from_resolved(
    al_run_id: str,
    body: ALRetrainRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.get(ALRun, al_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="AL run not found")
    authz.require_project_access(db, current_user, run.project_id, Role.DEVELOPER)

    body = body or ALRetrainRequest()

    # Must have at least one resolved item — retraining only makes sense once a
    # human has curated the uncertain samples.
    stats = resolution_stats(db, al_run_id)
    if stats["resolved"] < 1:
        raise HTTPException(status_code=409, detail="no resolved items to retrain on")

    # Prefer the dataset version the AL run was created against; fall back to the
    # request body.
    dataset_version_id = _run_dataset_version_id(run) or body.dataset_version_id
    if not dataset_version_id:
        raise HTTPException(status_code=400, detail="dataset_version_id could not be determined")

    task = body.task or _dataset_task_type(db, dataset_version_id) or "detect"

    kwargs: dict = {
        "task": task,
        "name": "AL Retrain",
        "owner_id": current_user.id,
        "cluster_id": body.cluster_id,
    }
    if body.framework:
        kwargs["framework"] = body.framework
    if body.base_model:
        kwargs["base_model"] = body.base_model
    if body.params:
        kwargs["params"] = body.params

    try:
        result = training_service.launch_training(db, run.project_id, dataset_version_id, **kwargs)
    except training_service.TaskTypeMismatch as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except training_service.TrainingDispatchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    train_run_id = result.get("experimentId") or result.get("id")
    run.last_train_run_id = train_run_id
    db.add(run)
    db.commit()

    return {
        "al_run_id": run.id,
        "train_run_id": train_run_id,
        "job_id": result.get("jobId") or result.get("id"),
        "status": result.get("status", "queued"),
        "resolved_count": stats["resolved"],
    }
