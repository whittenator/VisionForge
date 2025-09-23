from pydantic import BaseModel


class DatasetCreate(BaseModel):
    name: str

class Dataset(BaseModel):
    id: str
    project_id: str
    name: str
    activeVersionId: str
