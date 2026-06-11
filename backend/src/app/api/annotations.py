from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.annotation import REVIEW_STATUSES, Annotation
from app.models.asset import Asset
from app.models.user import User
from app.models.workspace import Role
from app.services import authz, inference_service, suggestion_service
from app.services.annotation_service import (
    AnnotationError,
    VersionConflictError,
    _ann_dict,
    bulk_save,
    create_annotation,
    delete_annotation,
    get_asset_annotations,
    get_history,
    list_review_queue,
    mark_asset_labeled,
    review_summary,
    set_review,
    update_annotation,
)

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


def _require_asset_dataset_access(db: Session, user: User, asset_id: str, min_role: Role) -> None:
    """Enforce dataset-level access for an asset.

    Missing assets are left for the service layer to report (it already
    returns its own 400/404s), so existing status codes are preserved.
    """
    asset = db.get(Asset, asset_id)
    if asset is not None:
        authz.require_dataset_access(db, user, asset.dataset_id, min_role)


def _require_annotation_access(db: Session, user: User, annotation_id: str, min_role: Role) -> None:
    ann = db.get(Annotation, annotation_id)
    if ann is not None:
        _require_asset_dataset_access(db, user, ann.asset_id, min_role)


class AnnotationCreate(BaseModel):
    asset_id: str
    type: str  # "box" | "polygon" | "keypoint" | "classification"
    geometry: dict
    class_name: str | None = None


class AnnotationUpdate(BaseModel):
    geometry: dict | None = None
    class_name: str | None = None
    expected_version: int | None = None


class BulkCreate(BaseModel):
    client_id: str | None = None  # client correlation id (e.g. tempId)
    asset_id: str
    type: str
    geometry: dict
    class_name: str | None = None


class BulkUpdate(BaseModel):
    id: str
    geometry: dict | None = None
    class_name: str | None = None
    expected_version: int | None = None


class BulkSaveRequest(BaseModel):
    creates: list[BulkCreate] = Field(default_factory=list)
    updates: list[BulkUpdate] = Field(default_factory=list)
    deletes: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    review_status: str  # "approved" | "rejected" | "unreviewed"
    notes: str | None = None


@router.post("", status_code=201)
def create(
    body: AnnotationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_asset_dataset_access(db, current_user, body.asset_id, Role.ANNOTATOR)
    try:
        ann = create_annotation(
            db,
            asset_id=body.asset_id,
            author_id=current_user.id,
            type=body.type,
            geometry=body.geometry,
            class_name=body.class_name,
        )
    except AnnotationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ann_dict(ann)


@router.put("/{annotation_id}")
def update(
    annotation_id: str = Path(...),
    body: AnnotationUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_annotation_access(db, current_user, annotation_id, Role.ANNOTATOR)
    try:
        ann = update_annotation(
            db,
            annotation_id,
            geometry=body.geometry,
            class_name=body.class_name,
            expected_version=body.expected_version,
        )
    except VersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AnnotationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return _ann_dict(ann)


@router.delete("/{annotation_id}", status_code=204)
def delete(
    annotation_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_annotation_access(db, current_user, annotation_id, Role.ANNOTATOR)
    if not delete_annotation(db, annotation_id):
        raise HTTPException(status_code=404, detail="Annotation not found")


@router.post("/bulk")
def bulk(
    body: BulkSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply many annotation mutations in one round-trip.

    The annotator uses this to flush all dirty edits in a single request
    instead of one PUT per dirty annotation. Returns per-entry status so the
    UI can highlight conflicts (HTTP 409 equivalents) without rolling back
    successful entries.
    """
    asset_ids = {c.asset_id for c in body.creates}
    ann_ids = {u.id for u in body.updates} | set(body.deletes)
    for ann_id in ann_ids:
        ann = db.get(Annotation, ann_id)
        if ann is not None:
            asset_ids.add(ann.asset_id)
    dataset_ids: set[str] = set()
    for asset_id in asset_ids:
        asset = db.get(Asset, asset_id)
        if asset is not None:
            dataset_ids.add(asset.dataset_id)
    for dataset_id in dataset_ids:
        authz.require_dataset_access(db, current_user, dataset_id, Role.ANNOTATOR)
    return bulk_save(
        db,
        author_id=current_user.id,
        creates=[c.model_dump() for c in body.creates],
        updates=[u.model_dump() for u in body.updates],
        deletes=body.deletes,
    )


@router.post("/{annotation_id}/review")
def review(
    body: ReviewRequest,
    annotation_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.review_status not in REVIEW_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"review_status must be one of {list(REVIEW_STATUSES)}",
        )
    _require_annotation_access(db, current_user, annotation_id, Role.ANNOTATOR)
    try:
        ann = set_review(
            db,
            annotation_id,
            review_status=body.review_status,
            reviewer_id=current_user.id,
            notes=body.notes,
        )
    except AnnotationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return _ann_dict(ann)


@router.get("/{annotation_id}/history")
def history(
    annotation_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import json as _json

    _require_annotation_access(db, current_user, annotation_id, Role.VIEWER)
    rows = get_history(db, annotation_id)
    out = []
    for h in rows:
        item = dict(h)
        g = item.get("geometry")
        if isinstance(g, str):
            try:
                item["geometry"] = _json.loads(g)
            except Exception:
                pass
        out.append(item)
    return out


@router.get("/assets/{asset_id}")
def list_for_asset(
    asset_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_asset_dataset_access(db, current_user, asset_id, Role.VIEWER)
    anns = get_asset_annotations(db, asset_id)
    return [_ann_dict(a) for a in anns]


@router.post("/assets/{asset_id}/mark-labeled", status_code=200)
def mark_labeled(
    asset_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_asset_dataset_access(db, current_user, asset_id, Role.ANNOTATOR)
    mark_asset_labeled(db, asset_id)
    return {"status": "labeled"}


@router.get("/datasets/{dataset_id}/review")
def review_queue(
    dataset_id: str = Path(...),
    version_id: str | None = Query(None),
    review_status: str | None = Query(None),
    flagged: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List annotations for a dataset's review queue."""
    authz.require_dataset_access(db, current_user, dataset_id, Role.VIEWER)
    try:
        items, total = list_review_queue(
            db,
            dataset_id=dataset_id,
            version_id=version_id,
            review_status=review_status,
            flagged=flagged,
            page=page,
            page_size=page_size,
        )
    except AnnotationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/datasets/{dataset_id}/review/summary")
def review_queue_summary(
    dataset_id: str = Path(...),
    version_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    authz.require_dataset_access(db, current_user, dataset_id, Role.VIEWER)
    return review_summary(db, dataset_id=dataset_id, version_id=version_id)


class SuggestRequest(BaseModel):
    asset_id: str
    artifact_id: str | None = None
    score_threshold: float = Field(0.25, ge=0.0, le=1.0)


@router.post("/suggest")
def suggest(
    body: SuggestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run a trained model on an asset and return proposed annotations.

    Suggestions are not persisted; the annotator overlays them and saves any
    accepted ones through the normal bulk path. 404 when no model is available,
    502 when inference fails.
    """
    _require_asset_dataset_access(db, current_user, body.asset_id, Role.ANNOTATOR)
    try:
        artifact, suggestions = suggestion_service.suggest_annotations(
            db,
            asset_id=body.asset_id,
            artifact_id=body.artifact_id,
            score_threshold=body.score_threshold,
        )
    except suggestion_service.NoModelError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except suggestion_service.SuggestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except inference_service.InferenceError as exc:
        raise HTTPException(status_code=502, detail=f"inference failed: {exc}") from exc

    return {
        "artifact": {
            "id": artifact.id,
            "name": artifact.name,
            "version": artifact.version,
        },
        "suggestions": [
            {
                "type": s.type,
                "geometry": s.geometry,
                "class_name": s.class_name,
                "score": s.score,
            }
            for s in suggestions
        ],
    }


@router.get("/suggest/artifacts")
def suggest_artifacts(
    dataset_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List models trained on this dataset, newest first (override dropdown)."""
    authz.require_dataset_access(db, current_user, dataset_id, Role.VIEWER)
    arts = suggestion_service.candidate_artifacts_for_dataset(db, dataset_id)
    return {
        "items": [
            {
                "id": a.id,
                "name": a.name,
                "version": a.version,
                "format": a.format,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in arts
        ]
    }


class ErrorMineRequest(BaseModel):
    artifact_id: str
    dataset_version_id: str
    iou_threshold: float = 0.5
    score_threshold: float = 0.25
    max_assets: int = 0


@router.post("/error-mine", status_code=202)
def queue_error_mining(
    body: ErrorMineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Queue an error-mining run that flags annotations disagreeing with predictions."""
    from app.jobs.celery_app import celery_app
    from app.models.artifact import ModelArtifact
    from app.models.dataset_version import DatasetVersion
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
        "iouThreshold": body.iou_threshold,
        "scoreThreshold": body.score_threshold,
        "maxAssets": body.max_assets,
    }
    job = create_job(db, "error_mining", payload)
    payload["jobId"] = job.id
    try:
        celery_app.send_task("app.jobs.tasks.error_mining.mine_errors", args=[payload])
    except Exception as exc:
        # Don't leave a phantom queued job in the dashboard if the broker is
        # unavailable — flip it to failed and surface 503 so the UI knows.
        try:
            update_job_status(db, job.id, status="failed", progress=0.0)
        except Exception:
            pass
        raise HTTPException(
            status_code=503, detail=f"failed to dispatch error-mining task: {exc}"
        ) from exc
    return {"jobId": job.id, "status": "queued"}
