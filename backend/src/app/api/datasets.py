from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.dataset import ClassMap, Dataset
from app.models.dataset_version import DatasetVersion
from app.models.user import User
from app.services.dataset_service import snapshot_version
from app.services.project_dataset_service import create_dataset as svc_create_dataset

router = APIRouter(prefix="/api", tags=["datasets"])


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None
    classes: list[str] | None = None  # initial class list


class SnapshotRequest(BaseModel):
    notes: str | None = None


class ClassesUpdate(BaseModel):
    classes: list[str]


@router.get("/datasets")
def list_datasets(
    project_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Dataset)
    if project_id:
        q = q.where(Dataset.project_id == project_id)
    datasets = list(db.scalars(q).all())
    result = []
    for d in datasets:
        latest_v = db.scalars(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == d.id)
            .order_by(DatasetVersion.version.desc())
            .limit(1)
        ).first()
        result.append(
            {
                "id": d.id,
                "project_id": d.project_id,
                "name": d.name,
                "description": d.description,
                "latest_version": latest_v.version if latest_v else None,
                "latest_version_id": latest_v.id if latest_v else None,
                "asset_count": latest_v.asset_count if latest_v else 0,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
        )
    return result


@router.get("/datasets/{dataset_id}")
def get_dataset(
    dataset_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = db.get(Dataset, dataset_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dataset not found")
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
    return {
        "id": d.id,
        "project_id": d.project_id,
        "name": d.name,
        "description": d.description,
        "classes": classes,
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
    d, v = svc_create_dataset(db, project_id, body.name, body.description)
    # Create ClassMap if classes provided
    if body.classes:
        cm = ClassMap(project_id=project_id, classes=json.dumps(body.classes))
        db.add(cm)
        db.flush()
        d.class_map_id = cm.id
        db.add(d)
        db.commit()
    return {"id": d.id, "project_id": d.project_id, "name": d.name, "activeVersionId": v.id}


@router.get("/datasets/{dataset_id}/versions")
def list_versions(
    dataset_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    d = db.get(Dataset, dataset_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dataset not found")
    v = snapshot_version(db, dataset_id, notes=body.notes)
    return {
        "id": v.id,
        "version": v.version,
        "asset_count": v.asset_count,
        "locked": v.locked,
    }


@router.put("/datasets/{dataset_id}/classes")
def update_classes(
    dataset_id: str = Path(...),
    body: ClassesUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = db.get(Dataset, dataset_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dataset not found")
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
