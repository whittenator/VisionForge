from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.annotation import REVIEW_STATUSES
from app.models.user import User
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
    anns = get_asset_annotations(db, asset_id)
    return [_ann_dict(a) for a in anns]


@router.post("/assets/{asset_id}/mark-labeled", status_code=200)
def mark_labeled(
    asset_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    return review_summary(db, dataset_id=dataset_id, version_id=version_id)


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

    if not db.get(ModelArtifact, body.artifact_id):
        raise HTTPException(status_code=400, detail="artifact not found")
    if not db.get(DatasetVersion, body.dataset_version_id):
        raise HTTPException(status_code=400, detail="dataset version not found")

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
