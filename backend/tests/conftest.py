# ruff: noqa: E402
import os
import sys
from collections.abc import Generator

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
    from app.services.auth import register
    from sqlalchemy import select
    from app.models.user import User

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
