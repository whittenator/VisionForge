from __future__ import annotations

from typing import Any

# Thin wrapper to align with planned file layout in tasks.md
from app.services.storage import presign_put_url


def get_presigned_upload(
    dataset_version_id: str, filename: str, content_type: str | None = None
) -> dict[str, Any]:
    """
    Contract:
    - inputs: dataset_version_id, filename, optional content_type
    - output: { url: str, fields: dict }
    Delegates to storage.presign_put_url so tests and behavior remain identical.
    """
    return presign_put_url(dataset_version_id, filename, content_type)
