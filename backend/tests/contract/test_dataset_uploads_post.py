import os
import sys
from fastapi.testclient import TestClient

CURRENT_DIR = os.path.dirname(__file__)
SRC_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "src"))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from app.main import app

client = TestClient(app)


def test_dataset_uploads_contract_uses_ingest_upload_url():
    r = client.post(
        "/api/ingest/upload-url",
        json={"datasetVersionId": "v1", "filename": "a.jpg", "contentType": "image/jpeg"},
    )
    assert r.status_code == 200
    assert "url" in r.json()
