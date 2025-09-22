from pydantic import BaseModel


class DatasetCreate(BaseModel):
    name: str
    media_type: str

class Dataset(BaseModel):
    id: str
    project_id: str
    name: str
    media_type: str
    activeVersionId: str
