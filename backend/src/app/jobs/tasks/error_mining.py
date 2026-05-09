"""Celery task: flag annotations whose model predictions disagree.

Runs an existing artifact over labelled assets in a dataset version. For
each ground-truth annotation, finds the best-IoU same-class prediction. If
the best IoU is below ``iou_threshold`` the annotation is flagged with a
short reason; otherwise the flag is cleared.

The intent is to surface likely mislabels in the review queue without
requiring a full evaluation run.

Heavy ML deps are imported lazily so the module is safe to load in tests
where those wheels are absent.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any

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


def _iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = max(0.0, aw) * max(0.0, ah) + max(0.0, bw) * max(0.0, bh) - inter
    return inter / union if union > 0 else 0.0


def _predict_boxes(artifact, asset, score_threshold: float) -> list[dict[str, Any]]:
    """Run the cached inference service against ``asset``. Returns det dicts."""
    from urllib.request import urlopen

    from app.services import inference_service, storage

    image_bytes: bytes | None = None
    try:
        if asset.uri.startswith(("http://", "https://")):
            with urlopen(asset.uri, timeout=10) as response:  # noqa: S310
                image_bytes = response.read()
        elif asset.uri:
            client = storage.get_minio_client()
            bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
            resp = client.get_object(bucket, asset.uri)
            try:
                image_bytes = resp.read()
            finally:
                resp.close()
                resp.release_conn()
    except Exception:
        return []
    if not image_bytes:
        return []
    try:
        result = inference_service.predict(artifact, image_bytes, score_threshold=score_threshold)
    except Exception:
        return []
    return list(result.get("detections") or [])


def _flag_annotation(db, ann, *, reason: str | None) -> None:
    if reason is None:
        if ann.flagged:
            ann.flagged = False
            ann.flag_reason = None
            db.add(ann)
    else:
        ann.flagged = True
        ann.flag_reason = reason[:255]
        db.add(ann)


@shared_task(name="app.jobs.tasks.error_mining.mine_errors")
def mine_errors(payload: dict) -> dict:
    job_id = payload.get("jobId")
    artifact_id = payload.get("artifactId")
    version_id = payload.get("datasetVersionId")
    iou_threshold = float(payload.get("iouThreshold", 0.5))
    score_threshold = float(payload.get("scoreThreshold", 0.25))
    max_assets = int(payload.get("maxAssets", 0)) or None

    db = _make_session()
    try:
        from sqlalchemy import select

        from app.models.annotation import Annotation
        from app.models.artifact import ModelArtifact
        from app.models.asset import Asset
        from app.services.jobs_service import update_job_status

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.05)

        artifact = db.get(ModelArtifact, artifact_id)
        if not artifact:
            raise RuntimeError("artifact not found")

        assets = list(
            db.scalars(
                select(Asset)
                .where(Asset.version_id == version_id)
                .where(Asset.label_status.in_(("labeled", "in_progress")))
            ).all()
        )
        if max_assets:
            assets = assets[:max_assets]

        flagged = 0
        cleared = 0
        scanned = 0

        for i, asset in enumerate(assets):
            anns = list(
                db.scalars(
                    select(Annotation)
                    .where(Annotation.asset_id == asset.id)
                    .where(Annotation.type == "box")
                ).all()
            )
            if not anns:
                continue
            preds = _predict_boxes(artifact, asset, score_threshold)
            # Group preds by class for fast lookup
            by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for p in preds:
                by_class[p.get("class") or ""].append(p)

            for ann in anns:
                scanned += 1
                try:
                    g = json.loads(ann.geometry)
                    gt_box = (
                        float(g.get("x", 0)),
                        float(g.get("y", 0)),
                        float(g.get("w", 0)),
                        float(g.get("h", 0)),
                    )
                except Exception:
                    continue
                cls = ann.class_name or ""
                same_class = by_class.get(cls, [])
                best_iou = 0.0
                for p in same_class:
                    bbox = p.get("bbox") or [0.0, 0.0, 0.0, 0.0]
                    iou = _iou(tuple(bbox), gt_box)
                    if iou > best_iou:
                        best_iou = iou
                if best_iou < iou_threshold:
                    if best_iou == 0.0:
                        reason = f"no model prediction for class '{cls}' on this asset"
                    else:
                        reason = f"best IoU {best_iou:.2f} < threshold {iou_threshold:.2f}"
                    _flag_annotation(db, ann, reason=reason)
                    flagged += 1
                else:
                    if ann.flagged:
                        cleared += 1
                    _flag_annotation(db, ann, reason=None)

            if (i + 1) % 10 == 0:
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
        return {
            "status": "succeeded",
            "scanned": scanned,
            "flagged": flagged,
            "cleared": cleared,
        }
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
