import os
import sys

from sqlalchemy import create_engine, inspect


def test_tables_exist(tmp_path):
    # Ensure backend/src is importable from this file location
    current_dir = os.path.dirname(__file__)
    src_path = os.path.abspath(os.path.join(current_dir, "..", "..", "src"))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from app import models as _models  # noqa: F401
    from app.db.base import Base

    # Create a temp SQLite DB and create all tables from metadata
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path}/unit.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)

    expected = {
        "projects",
        "datasets",
        "dataset_versions",
        "assets",
        "users",
        "workspaces",
        "memberships",
        "class_maps",
        "annotation_schemas",
        "annotations",
        "tracks",
        "experiment_runs",
        "model_artifacts",
        "invitations",
        "notifications",
        "al_runs",
        "al_items",
        "jobs",
        "audits",
        "audit_events",
    }

    actual_tables = set(insp.get_table_names())
    
    assert expected.issubset(actual_tables)
