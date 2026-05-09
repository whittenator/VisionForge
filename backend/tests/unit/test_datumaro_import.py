import io
import json
import zipfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models as _models  # noqa: F401
from app.db.base import Base
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.services.datumaro_service import (
    DatumaroError,
    export_archive,
    import_archive,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    s = Session()
    s.add(Dataset(id="d1", project_id="p1", name="d", description=""))
    s.commit()
    s.add(DatasetVersion(id="v1", dataset_id="d1", version=1))
    s.commit()
    try:
        yield s
    finally:
        s.close()


def _zip_files(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_unsupported_format_raises(db):
    with pytest.raises(DatumaroError):
        import_archive(
            db,
            dataset_id="d1",
            version_id="v1",
            archive_bytes=b"",
            fmt="parquet",
        )


def test_coco_import_creates_assets_and_annotations(db):
    coco = {
        "images": [
            {"id": 1, "file_name": "a.jpg", "width": 100, "height": 100},
            {"id": 2, "file_name": "b.jpg", "width": 100, "height": 100},
        ],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1, "bbox": [10, 10, 20, 20]},
            {"id": 2, "image_id": 2, "category_id": 2, "bbox": [5, 5, 30, 30]},
        ],
        "categories": [{"id": 1, "name": "cat"}, {"id": 2, "name": "dog"}],
    }
    archive = _zip_files({"annotations.json": json.dumps(coco).encode()})
    summary = import_archive(
        db,
        dataset_id="d1",
        version_id="v1",
        archive_bytes=archive,
        fmt="coco",
        image_uri_base="datasets/d1/imported",
    )
    assert summary.asset_count == 2
    assert summary.annotation_count == 2
    assert "cat" in summary.classes and "dog" in summary.classes


def test_yolo_import_with_classes(db):
    archive = _zip_files(
        {
            "classes.txt": b"car\nbike\n",
            "images/img1.jpg": b"\xff\xd8\xff\xe0",  # not a valid jpeg, but enough to be detected
            "labels/img1.txt": b"0 0.5 0.5 0.4 0.4\n1 0.2 0.2 0.1 0.1\n",
        }
    )
    summary = import_archive(
        db,
        dataset_id="d1",
        version_id="v1",
        archive_bytes=archive,
        fmt="yolo",
    )
    assert summary.asset_count == 1
    assert summary.annotation_count == 2
    assert summary.classes == ["car", "bike"]


def test_export_roundtrip_coco(db):
    # First import a small COCO so we have data to export
    coco = {
        "images": [{"id": 1, "file_name": "a.jpg", "width": 100, "height": 100}],
        "annotations": [{"id": 1, "image_id": 1, "category_id": 1, "bbox": [1, 2, 3, 4]}],
        "categories": [{"id": 1, "name": "car"}],
    }
    archive = _zip_files({"annotations.json": json.dumps(coco).encode()})
    import_archive(db, dataset_id="d1", version_id="v1", archive_bytes=archive, fmt="coco")
    blob = export_archive(db, dataset_id="d1", version_id="v1", fmt="coco")
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = zf.namelist()
        assert "annotations.json" in names
        data = json.loads(zf.read("annotations.json"))
        assert len(data["images"]) == 1
        assert len(data["annotations"]) == 1
        assert data["categories"][0]["name"] == "car"


def test_export_yolo_writes_labels_and_classes(db):
    coco = {
        "images": [{"id": 1, "file_name": "a.jpg", "width": 100, "height": 100}],
        "annotations": [{"id": 1, "image_id": 1, "category_id": 1, "bbox": [10, 20, 30, 40]}],
        "categories": [{"id": 1, "name": "car"}],
    }
    archive = _zip_files({"annotations.json": json.dumps(coco).encode()})
    import_archive(db, dataset_id="d1", version_id="v1", archive_bytes=archive, fmt="coco")
    blob = export_archive(db, dataset_id="d1", version_id="v1", fmt="yolo")
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = zf.namelist()
        assert "classes.txt" in names
        assert any(n.startswith("labels/") for n in names)
        cls = zf.read("classes.txt").decode().strip()
        assert "car" in cls


def test_export_yolo_disambiguates_colliding_stems(db):
    """Two assets with the same filename stem must produce distinct label files."""
    # Import two images that share the same basename in different folders.
    coco = {
        "images": [
            {"id": 1, "file_name": "train/img.jpg", "width": 100, "height": 100},
            {"id": 2, "file_name": "val/img.jpg", "width": 100, "height": 100},
        ],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1, "bbox": [1, 2, 3, 4]},
            {"id": 2, "image_id": 2, "category_id": 1, "bbox": [5, 6, 7, 8]},
        ],
        "categories": [{"id": 1, "name": "car"}],
    }
    archive = _zip_files({"annotations.json": json.dumps(coco).encode()})
    import_archive(db, dataset_id="d1", version_id="v1", archive_bytes=archive, fmt="coco")

    blob = export_archive(db, dataset_id="d1", version_id="v1", fmt="yolo")
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        label_files = [n for n in zf.namelist() if n.startswith("labels/")]
        # Both labels must be present — neither must overwrite the other.
        assert len(label_files) == 2
        assert len(set(label_files)) == 2
        # Manifest carries the asset → label mapping for reconstruction.
        manifest = zf.read("manifest.csv").decode().splitlines()
        assert manifest[0] == "asset_id,uri,label_file"
        assert len(manifest) == 3
