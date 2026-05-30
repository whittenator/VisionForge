from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.asset import Asset
from app.services import split_service


@pytest.fixture()
def db():
    # Importing the models registers their tables on Base.metadata.
    import app.models.annotation  # noqa: F401
    import app.models.dataset  # noqa: F401
    import app.models.dataset_version  # noqa: F401

    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield session
    session.close()


def _seed_assets(db, n: int, version_id: str = "v1") -> None:
    for i in range(n):
        db.add(
            Asset(
                id=f"a{i:04d}",
                dataset_id="d1",
                version_id=version_id,
                uri=f"key/{i}.jpg",
                mime_type="image/jpeg",
            )
        )
    db.commit()


def test_normalize_ratios_normalizes_and_validates():
    assert split_service.normalize_ratios(8, 1, 1) == pytest.approx((0.8, 0.1, 0.1))
    # Already-fractional ratios are preserved.
    assert split_service.normalize_ratios(0.7, 0.2, 0.1) == pytest.approx((0.7, 0.2, 0.1))
    with pytest.raises(split_service.SplitConfigError):
        split_service.normalize_ratios(0, 0, 0)
    with pytest.raises(split_service.SplitConfigError):
        split_service.normalize_ratios(-1, 1, 1)


def test_resolve_split_is_deterministic_and_seed_sensitive():
    r1 = split_service.resolve_split("asset-x", (0.8, 0.1, 0.1), 42)
    r2 = split_service.resolve_split("asset-x", (0.8, 0.1, 0.1), 42)
    assert r1 == r2
    assert r1 in split_service.VALID_SPLITS
    # A different seed should change at least some assignments.
    diffs = sum(
        split_service.resolve_split(f"a{i}", (0.34, 0.33, 0.33), 1)
        != split_service.resolve_split(f"a{i}", (0.34, 0.33, 0.33), 2)
        for i in range(200)
    )
    assert diffs > 0


def test_slice_counts_never_loses_items():
    for n in (0, 1, 7, 10, 99):
        tr, va, te = split_service._slice_counts(n, (0.8, 0.1, 0.1))
        assert tr + va + te == n
        assert min(tr, va, te) >= 0


def test_assign_splits_persists_and_summarizes(db):
    _seed_assets(db, 100)
    summary = split_service.assign_splits(
        db, "v1", train=0.8, val=0.1, test=0.1, seed=42, stratify=False
    )
    counts = summary["counts"]
    assert counts["train"] + counts["val"] + counts["test"] == 100
    assert counts["train"] == 80 and counts["val"] == 10 and counts["test"] == 10
    assert counts["unassigned"] == 0
    assert summary["seed"] == 42

    # Persisted onto meta_data and reflected by get_split_summary.
    a = db.get(Asset, "a0000")
    assert json.loads(a.meta_data)["split"] in split_service.VALID_SPLITS
    again = split_service.get_split_summary(db, "v1")
    assert again["counts"] == counts


def test_assign_splits_is_reproducible(db):
    _seed_assets(db, 50)
    split_service.assign_splits(db, "v1", seed=7, stratify=False)
    first = {a.id: split_service.asset_split(a) for a in db.query(Asset).all()}
    # Re-run with the same seed → identical assignment.
    split_service.assign_splits(db, "v1", seed=7, stratify=False)
    second = {a.id: split_service.asset_split(a) for a in db.query(Asset).all()}
    assert first == second


def test_asset_split_reads_meta_data():
    class FakeAsset:
        meta_data = json.dumps({"split": "TEST"})

    assert split_service.asset_split(FakeAsset()) == "test"

    class NoSplit:
        meta_data = json.dumps({"other": 1})

    assert split_service.asset_split(NoSplit()) is None
