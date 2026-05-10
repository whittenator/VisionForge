"""Celery task: precompute per-asset uncertainty scores for active learning.

The AL select endpoint (`/api/al/select`) only scores up to
``VF_AL_INLINE_SCORE_CAP`` assets inline so the API stays fast. For full-pool
scoring, dispatch this task — it runs the chosen artifact over every asset
in the version and stores the score (margin = ``1 - top_score``) into
``Asset.meta_data["uncertainty"]``. Subsequent ``/api/al/select`` calls will
read those cached values instead of running inference again.

Heavy ML deps are imported lazily so the module is safe to load in tests.
"""

from __future__ import annotations

import json
import os

try:
    from celery import shared_task  # type: ignore
except Exception:  # pragma: no cover

    def shared_task(*args, **kwargs):
        def _wrap(fn):
            return fn

        return _wrap


def _make_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./test.db")
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _top_score(result: dict | list) -> float:
    if isinstance(result, dict):
        cls_pred = result.get("classification")
        if isinstance(cls_pred, dict) and "score" in cls_pred:
            try:
                return float(cls_pred["score"])
            except Exception:
                pass
        if "top_score" in result:
            try:
                return float(result["top_score"])
            except Exception:
                pass
        boxes = result.get("detections") or result.get("predictions") or []
    elif isinstance(result, list):
        boxes = result
    else:
        boxes = []
    best = 0.0
    for b in boxes:
        score = b.get("score") or b.get("confidence") or 0.0
        try:
            score = float(score)
        except Exception:
            continue
        if score > best:
            best = score
    return best


@shared_task(name="app.jobs.tasks.al_uncertainty.score_assets")
def score_assets(payload: dict) -> dict:
    job_id = payload.get("jobId")
    artifact_id = payload.get("artifactId")
    version_id = payload.get("datasetVersionId")
    max_assets = int(payload.get("maxAssets", 0)) or None

    db = _make_session()
    scored = 0
    skipped = 0
    try:
        from sqlalchemy import select

        from app.models.artifact import ModelArtifact
        from app.models.asset import Asset
        from app.services import inference_service
        from app.services.asset_fetch import fetch_asset_bytes
        from app.services.jobs_service import update_job_status

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.05)

        artifact = db.get(ModelArtifact, artifact_id)
        if artifact is None:
            raise RuntimeError("artifact not found")

        assets = list(
            db.scalars(
                select(Asset)
                .where(Asset.version_id == version_id)
                .where(Asset.label_status.in_(("unlabeled", "unlabelled", "in_progress")))
            ).all()
        )
        if max_assets:
            assets = assets[:max_assets]

        for i, asset in enumerate(assets):
            image_bytes = fetch_asset_bytes(asset.uri)
            if not image_bytes:
                skipped += 1
                continue
            try:
                result = inference_service.predict(artifact, image_bytes, score_threshold=0.0)
            except Exception:
                skipped += 1
                continue
            margin = 1.0 - _top_score(result)
            try:
                meta = json.loads(asset.meta_data) if asset.meta_data else {}
            except Exception:
                meta = {}
            if not isinstance(meta, dict):
                meta = {}
            meta["uncertainty"] = float(margin)
            meta["uncertainty_artifact_id"] = artifact.id
            asset.meta_data = json.dumps(meta)
            db.add(asset)
            scored += 1
            if (i + 1) % 25 == 0:
                db.commit()
                if job_id:
                    update_job_status(
                        db,
                        job_id,
                        status="running",
                        progress=0.1 + 0.85 * (i / max(1, len(assets))),
                    )

        db.commit()
        if job_id:
            update_job_status(db, job_id, status="succeeded", progress=1.0)
        return {"status": "succeeded", "scored": scored, "skipped": skipped}
    except Exception as exc:  # noqa: BLE001
        try:
            from app.services.jobs_service import update_job_status as _us

            if job_id:
                _us(db, job_id, status="failed", progress=0.0)
        except Exception:
            pass
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()
