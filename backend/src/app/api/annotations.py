from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.user import User
from app.services.annotation_service import (
    create_annotation,
    delete_annotation,
    get_asset_annotations,
    mark_asset_labeled,
    update_annotation,
)

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


class AnnotationCreate(BaseModel):
    asset_id: str
    type: str  # "box", "polygon", "classification", etc.
    geometry: dict
    class_name: str | None = None


class AnnotationUpdate(BaseModel):
    geometry: dict | None = None
    class_name: str | None = None


def _ann_to_dict(ann) -> dict:
    return {
        "id": ann.id,
        "asset_id": ann.asset_id,
        "type": ann.type,
        "geometry": json.loads(ann.geometry) if isinstance(ann.geometry, str) else ann.geometry,
        "class_name": ann.class_name,
        "author_id": ann.author_id,
        "created_at": ann.created_at.isoformat() if ann.created_at else None,
    }


@router.post("", status_code=201)
def create(
    body: AnnotationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ann = create_annotation(
        db,
        asset_id=body.asset_id,
        author_id=current_user.id,
        type=body.type,
        geometry=body.geometry,
        class_name=body.class_name,
    )
    return _ann_to_dict(ann)


@router.put("/{annotation_id}")
def update(
    annotation_id: str = Path(...),
    body: AnnotationUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ann = update_annotation(db, annotation_id, geometry=body.geometry, class_name=body.class_name)
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return _ann_to_dict(ann)


@router.delete("/{annotation_id}", status_code=204)
def delete(
    annotation_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not delete_annotation(db, annotation_id):
        raise HTTPException(status_code=404, detail="Annotation not found")


@router.get("/assets/{asset_id}")
def list_for_asset(
    asset_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    anns = get_asset_annotations(db, asset_id)
    return [_ann_to_dict(a) for a in anns]


@router.post("/assets/{asset_id}/mark-labeled", status_code=200)
def mark_labeled(
    asset_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mark_asset_labeled(db, asset_id)
    return {"status": "labeled"}
