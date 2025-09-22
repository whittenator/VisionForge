from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:  # ensure pgvector dialect registered if installed
    import pgvector.sqlalchemy  # type: ignore  # noqa: F401
except Exception:
    pass


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("POSTGRES_USER", "visionforge")
    pwd = os.getenv("POSTGRES_PASSWORD", "change-me")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "visionforge")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"

url = _db_url()
connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
engine = create_engine(url, pool_pre_ping=True, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
