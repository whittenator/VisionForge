
from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.dataset import Dataset, DatasetCreate
from app.services.project_dataset_service import create_dataset as svc_create_dataset

router = APIRouter(prefix="/api", tags=["datasets"])

@router.post("/datasets/{projectId}", response_model=Dataset, status_code=201)
def create_dataset(payload: DatasetCreate, projectId: str = Path(...), db: Session = Depends(get_db)):
    d, v = svc_create_dataset(db, projectId, payload.name, payload.media_type)
    return Dataset(
        id=d.id,
        project_id=d.project_id,
        name=d.name,
        media_type=d.media_type,
        activeVersionId=v.id,
    )
