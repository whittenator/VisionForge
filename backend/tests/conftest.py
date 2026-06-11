# ruff: noqa: E402
import os
import sys
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend/src is importable
CURRENT_DIR = os.path.dirname(__file__)
SRC_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "src"))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# Force SQLite file database for tests before importing app modules
# Use a single absolute DB file path for all engines/sessions
DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "test.db"))
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{DB_FILE}"
os.environ["SKIP_DB_MIGRATIONS"] = "true"
os.environ.setdefault("MINIO_DISABLED", "true")
os.environ.setdefault("S3_BUCKET", "visionforge")

from app import models as _models  # noqa: F401  # isort: skip
from app.db.base import Base
from app.db.deps import get_db
from app.main import app

# Ensure a fresh SQLite file DB each test run to avoid stale schemas
try:
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
except Exception:
    pass

engine = create_engine(f"sqlite+pysqlite:///{DB_FILE}", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)

# Seed a demo user for auth contract tests
try:
    from sqlalchemy import select

    from app.models.user import User
    from app.services.auth import register

    with TestingSessionLocal() as _db:
        exists = _db.scalar(select(User).where(User.email == "demo@example.com"))
        if not exists:
            register(_db, name="Demo User", email="demo@example.com", password="password123")
except Exception:
    # Keep tests running even if seeding fails; auth tests may handle absence
    pass


def override_get_db() -> Generator:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


# Many tests attach datasets/runs to a project id of "p" and exercise endpoints
# as a fake user. Object-level authz resolves a resource -> project -> workspace,
# so that project must exist in an accessible workspace. The default workspace
# (all-zero UUID) is open to every authenticated user, so seed "p" there.
DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000000"
try:
    from app.models.project import Project as _Project

    with TestingSessionLocal() as _db:
        if not _db.get(_Project, "p"):
            _db.add(
                _Project(
                    id="p",
                    name="Test Project",
                    slug="test-project-p",
                    workspace_id=DEFAULT_WORKSPACE_ID,
                )
            )
            _db.commit()
except Exception:
    pass


@pytest.fixture(autouse=True)
def _hermetic_celery(monkeypatch):
    """Unit tests must not reach a real broker.

    Patch ``celery_app.send_task`` to a no-op so job-launch services create
    their Job row and return "queued" without enqueueing (the dispatch-failure
    path is covered explicitly where it matters).
    """
    from unittest.mock import MagicMock

    from app.jobs import celery_app as _celery_mod

    monkeypatch.setattr(
        _celery_mod.celery_app, "send_task", MagicMock(return_value=None), raising=False
    )
    yield


def ensure_project(project_id: str, *, workspace_id: str = DEFAULT_WORKSPACE_ID) -> None:
    """Create a project (in the default, open workspace) if it doesn't exist."""
    from app.models.project import Project as _Project

    with TestingSessionLocal() as db:
        if not db.get(_Project, project_id):
            db.add(
                _Project(
                    id=project_id,
                    name=f"Project {project_id[:8]}",
                    slug=f"proj-{project_id[:12]}",
                    workspace_id=workspace_id,
                )
            )
            db.commit()
