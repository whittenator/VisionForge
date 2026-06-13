from __future__ import annotations

import json

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Response,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.asset import Asset
from app.models.dataset import ClassMap, Dataset
from app.models.dataset_version import DatasetVersion
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Membership, Role
from app.services import authz, datumaro_service
from app.services.dataset_service import snapshot_version
from app.services.project_dataset_service import create_dataset as svc_create_dataset

router = APIRouter(prefix="/api", tags=["datasets"])

# label_status values that count as "annotated" toward coverage.
_LABELED_STATUSES = ("labeled", "prelabeled")


def _member_workspace_ids(db: Session, user: User) -> list[str]:
    """Workspace ids the user belongs to, plus the shared default workspace."""
    ws_ids = {
        m.workspace_id
        for m in db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    }
    ws_ids.add(authz.DEFAULT_WORKSPACE_ID)
    return list(ws_ids)


def _coverage_for_version(db: Session, version_id: str | None) -> tuple[float, str]:
    """Return (coverage_pct, status) for a dataset version.

    Coverage is the share of assets whose ``label_status`` is labeled/prelabeled.
    The derived status drives the Datasets table badge:
      - 100% coverage           -> "ready"
      - 0% coverage             -> "review" (imported / awaiting a pass)
      - anything in between     -> "annotating"
    """
    if not version_id:
        return 0.0, "ready"

    rows = db.execute(
        select(Asset.label_status, func.count())
        .where(Asset.version_id == version_id)
        .group_by(Asset.label_status)
    ).all()
    counts = {status: count for status, count in rows}
    total = sum(counts.values())
    if total == 0:
        return 0.0, "ready"

    labeled = sum(counts.get(s, 0) for s in _LABELED_STATUSES)
    pct = round(labeled / total * 100, 1)
    if pct >= 100:
        status = "ready"
    elif pct <= 0:
        status = "review"
    else:
        status = "annotating"
    return pct, status


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None
    classes: list[str] | None = None  # initial class list
    task_type: str | None = None  # "detect" | "classify"


class SnapshotRequest(BaseModel):
    notes: str | None = None


class ClassesUpdate(BaseModel):
    classes: list[str]


class TaskTypeUpdate(BaseModel):
    task_type: str  # "detect" | "classify"


@router.get("/datasets")
def list_datasets(
    project_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = select(Dataset)
    if project_id:
        authz.require_project_access(db, current_user, project_id, Role.VIEWER)
        base = base.where(Dataset.project_id == project_id)
    elif not authz.is_superuser(db, current_user):
        base = base.join(Project, Dataset.project_id == Project.id).where(
            Project.workspace_id.in_(_member_workspace_ids(db, current_user))
        )

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    offset = (page - 1) * page_size
    datasets = list(
        db.scalars(base.order_by(Dataset.created_at.desc()).offset(offset).limit(page_size)).all()
    )

    items = []
    for d in datasets:
        latest_v = db.scalars(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == d.id)
            .order_by(DatasetVersion.version.desc())
            .limit(1)
        ).first()
        coverage_pct, status = _coverage_for_version(db, latest_v.id if latest_v else None)
        items.append(
            {
                "id": d.id,
                "project_id": d.project_id,
                "name": d.name,
                "description": d.description,
                "task_type": d.task_type,
                "latest_version": latest_v.version if latest_v else None,
                "latest_version_id": latest_v.id if latest_v else None,
                "asset_count": latest_v.asset_count if latest_v else 0,
                "coverage_pct": coverage_pct,
                "status": status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# NOTE: register the static `/datasets/formats` route BEFORE the dynamic
# `/datasets/{dataset_id}` route — otherwise FastAPI matches "formats" as a
# dataset id and returns 404.
@router.get("/datasets/formats")
def list_dataset_formats(
    current_user: User = Depends(get_current_user),
):
    return {"formats": list(datumaro_service.SUPPORTED_FORMATS)}


@router.get("/datasets/{dataset_id}")
def get_dataset(
    dataset_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = authz.require_dataset_access(db, current_user, dataset_id, Role.VIEWER)
    versions = list(
        db.scalars(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == d.id)
            .order_by(DatasetVersion.version.desc())
        ).all()
    )
    class_map = db.get(ClassMap, d.class_map_id) if d.class_map_id else None
    classes: list = []
    if class_map:
        try:
            classes = json.loads(class_map.classes)
        except Exception:
            classes = []
    # The newest version (latest) and the newest editable/unlocked version
    # (open) — the UI writes new imagery/imports into the open version.
    latest_v = versions[0] if versions else None
    open_v = next((v for v in versions if not v.locked), None)
    return {
        "id": d.id,
        "project_id": d.project_id,
        "name": d.name,
        "description": d.description,
        "task_type": d.task_type,
        "classes": classes,
        "latest_version_id": latest_v.id if latest_v else None,
        "open_version_id": open_v.id if open_v else None,
        "versions": [
            {
                "id": v.id,
                "version": v.version,
                "asset_count": v.asset_count,
                "locked": v.locked,
                "notes": v.notes,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ],
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.post("/datasets/{project_id}", status_code=201)
def create_dataset(
    body: DatasetCreate,
    project_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    authz.require_project_access(db, current_user, project_id, Role.DEVELOPER)
    try:
        d, v = svc_create_dataset(
            db,
            project_id,
            body.name,
            body.description,
            task_type=body.task_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Create ClassMap if classes provided
    if body.classes:
        cm = ClassMap(project_id=project_id, classes=json.dumps(body.classes))
        db.add(cm)
        db.flush()
        d.class_map_id = cm.id
        db.add(d)
        db.commit()
    return {
        "id": d.id,
        "project_id": d.project_id,
        "name": d.name,
        "task_type": d.task_type,
        "activeVersionId": v.id,
    }


@router.patch("/datasets/{dataset_id}/task-type")
def update_dataset_task_type(
    body: TaskTypeUpdate,
    dataset_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.project_dataset_service import VALID_TASK_TYPES

    if body.task_type not in VALID_TASK_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"task_type must be one of {list(VALID_TASK_TYPES)}",
        )
    d = authz.require_dataset_access(db, current_user, dataset_id, Role.DEVELOPER)
    d.task_type = body.task_type
    db.add(d)
    db.commit()
    return {"id": d.id, "task_type": d.task_type}


@router.get("/datasets/{dataset_id}/versions")
def list_versions(
    dataset_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    authz.require_dataset_access(db, current_user, dataset_id, Role.VIEWER)
    versions = list(
        db.scalars(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version.desc())
        ).all()
    )
    return [
        {
            "id": v.id,
            "version": v.version,
            "asset_count": v.asset_count,
            "locked": v.locked,
            "notes": v.notes,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


@router.post("/datasets/{dataset_id}/snapshot", status_code=201)
def create_snapshot(
    dataset_id: str = Path(...),
    body: SnapshotRequest = SnapshotRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    authz.require_dataset_access(db, current_user, dataset_id, Role.DEVELOPER)
    v = snapshot_version(db, dataset_id, notes=body.notes)
    return {
        "id": v.id,
        "version": v.version,
        "asset_count": v.asset_count,
        "locked": v.locked,
    }


@router.post("/datasets/{dataset_id}/import", status_code=201)
async def import_dataset(
    dataset_id: str = Path(...),
    file: UploadFile = File(...),
    fmt: str = Form("coco"),
    version_id: str | None = Form(None),
    image_uri_base: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import an annotation archive (zip) in COCO/YOLO/Pascal VOC/CVAT/etc.

    If `version_id` is omitted, a fresh draft version is created. The archive
    must contain images plus annotation files for the chosen format.
    """
    authz.require_dataset_access(db, current_user, dataset_id, Role.DEVELOPER)

    # Resolve target version
    if version_id:
        version = db.get(DatasetVersion, version_id)
        if not version or version.dataset_id != dataset_id:
            raise HTTPException(status_code=404, detail="Version not found")
        if version.locked:
            raise HTTPException(status_code=409, detail="Version is locked")
    else:
        latest = db.scalars(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version.desc())
            .limit(1)
        ).first()
        next_v = (latest.version + 1) if latest else 1
        version = DatasetVersion(dataset_id=dataset_id, version=next_v)
        db.add(version)
        db.commit()
        db.refresh(version)

    archive_bytes = await file.read()
    if not archive_bytes:
        raise HTTPException(status_code=400, detail="empty archive")

    try:
        summary = datumaro_service.import_archive(
            db,
            dataset_id=dataset_id,
            version_id=version.id,
            archive_bytes=archive_bytes,
            fmt=fmt,
            image_uri_base=image_uri_base,
        )
    except datumaro_service.DatumaroError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "dataset_id": dataset_id,
        "version_id": version.id,
        "format": fmt,
        "asset_count": summary.asset_count,
        "annotation_count": summary.annotation_count,
        "classes": summary.classes,
        "warnings": summary.warnings,
    }


@router.get("/datasets/{dataset_id}/export")
def export_dataset(
    dataset_id: str = Path(...),
    version_id: str = Query(...),
    fmt: str = Query("coco"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export a dataset version as a zip archive in the requested format."""
    authz.require_dataset_access(db, current_user, dataset_id, Role.DEVELOPER)
    try:
        archive = datumaro_service.export_archive(
            db, dataset_id=dataset_id, version_id=version_id, fmt=fmt
        )
    except datumaro_service.DatumaroError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    headers = {
        "Content-Disposition": f'attachment; filename="dataset-{dataset_id}-{version_id}-{fmt}.zip"'
    }
    return Response(content=archive, media_type="application/zip", headers=headers)


@router.put("/datasets/{dataset_id}/classes")
def update_classes(
    dataset_id: str = Path(...),
    body: ClassesUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = authz.require_dataset_access(db, current_user, dataset_id, Role.DEVELOPER)
    if d.class_map_id:
        cm = db.get(ClassMap, d.class_map_id)
        if cm:
            cm.classes = json.dumps(body.classes)
            db.add(cm)
    else:
        cm = ClassMap(project_id=d.project_id, classes=json.dumps(body.classes))
        db.add(cm)
        db.flush()
        d.class_map_id = cm.id
        db.add(d)
    db.commit()
    return {"classes": body.classes}
