from __future__ import annotations

import os
from typing import Any

from app.services.storage import presign_put_url


def get_presigned_upload(
    dataset_version_id: str, filename: str, content_type: str | None = None
) -> dict[str, Any]:
    """Return presigned PUT URL and the MinIO object key for the frontend to confirm after upload.

    Returns:
        { url: str, fields: dict, objectKey: str }
    """
    bucket = os.getenv("S3_BUCKET", "visionforge")
    object_key = f"datasets/{dataset_version_id}/{filename}"
    result = presign_put_url(dataset_version_id, filename, content_type)
    result["objectKey"] = object_key
    return result
