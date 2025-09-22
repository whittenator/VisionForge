
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.project import Project, ProjectCreate
from app.services.project_dataset_service import create_project as svc_create_project

router = APIRouter(prefix="/api", tags=["projects"])

@router.post("/projects", response_model=Project, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    p = svc_create_project(db, payload.name, payload.description)
    return Project(id=p.id, name=p.name, description=p.description)
