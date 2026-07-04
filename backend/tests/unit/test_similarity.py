from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (register every model on Base.metadata)
from app.db.base import Base
from app.models.asset import Asset
from app.services.similarity_service import find_duplicates, find_similar


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def _add_asset(db, dataset_id: str, embedding: list[float] | None) -> Asset:
    asset = Asset(
        id=str(uuid.uuid4()),
        dataset_id=dataset_id,
        uri=f"s3://bucket/{uuid.uuid4()}.jpg",
        mime_type="image/jpeg",
        embedding=embedding,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def _padded(prefix: list[float]) -> list[float]:
    """Pad a short vector out to the stored 512-dim column with zeros."""
    return prefix + [0.0] * (512 - len(prefix))


def test_find_similar_orders_by_cosine_distance(db):
    ds = "ds-1"
    query = _add_asset(db, ds, _padded([1.0, 0.0, 0.0]))
    near = _add_asset(db, ds, _padded([0.99, 0.05, 0.0]))  # almost identical direction
    mid = _add_asset(db, ds, _padded([1.0, 1.0, 0.0]))  # 45 degrees off
    far = _add_asset(db, ds, _padded([0.0, 1.0, 0.0]))  # orthogonal

    results = find_similar(db, query.id, k=10)

    # Query asset must be excluded.
    assert query.id not in {a.id for a, _ in results}
    # Nearest-first ordering.
    ordered_ids = [a.id for a, _ in results]
    assert ordered_ids == [near.id, mid.id, far.id]
    # Distances are non-decreasing and the closest is tiny.
    distances = [d for _, d in results]
    assert distances == sorted(distances)
    assert distances[0] < 0.01


def test_find_similar_scopes_to_dataset(db):
    query = _add_asset(db, "ds-a", _padded([1.0, 0.0]))
    same = _add_asset(db, "ds-a", _padded([0.9, 0.1]))
    _add_asset(db, "ds-b", _padded([1.0, 0.0]))  # identical but other dataset

    results = find_similar(db, query.id, k=10, dataset_id="ds-a")
    assert {a.id for a, _ in results} == {same.id}


def test_find_similar_ignores_null_embeddings(db):
    query = _add_asset(db, "ds", _padded([1.0, 0.0]))
    good = _add_asset(db, "ds", _padded([1.0, 0.0]))
    _add_asset(db, "ds", None)

    results = find_similar(db, query.id, k=10)
    assert [a.id for a, _ in results] == [good.id]


def test_find_similar_empty_when_query_has_no_embedding(db):
    query = _add_asset(db, "ds", None)
    _add_asset(db, "ds", _padded([1.0, 0.0]))
    assert find_similar(db, query.id) == []


def test_find_duplicates_flags_near_pairs(db):
    ds = "dup-ds"
    a = _add_asset(db, ds, _padded([1.0, 0.0, 0.0]))
    b = _add_asset(db, ds, _padded([1.0, 0.001, 0.0]))  # duplicate of a
    _add_asset(db, ds, _padded([0.0, 1.0, 0.0]))  # unrelated

    result = find_duplicates(db, ds, threshold=0.05)
    assert result["computed"] is True
    assert result["truncated"] is False
    assert result["total"] == 1
    pair = result["pairs"][0]
    assert {pair["asset_a"].id, pair["asset_b"].id} == {a.id, b.id}
    assert pair["distance"] <= 0.05


def test_find_duplicates_not_computed_with_few_embeddings(db):
    ds = "sparse"
    _add_asset(db, ds, _padded([1.0, 0.0]))
    _add_asset(db, ds, None)

    result = find_duplicates(db, ds)
    assert result["computed"] is False
    assert result["pairs"] == []
    assert result["total"] == 0
