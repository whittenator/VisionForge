"""Celery training task — a thin orchestrator over the pluggable trainers.

Framework-agnostic scaffolding (load the run, resolve the dataset + split, set
up MinIO, report progress/metrics, persist the model artifact and plots, mark
the job done) lives here. The library-specific training is delegated to a
:class:`~app.services.training.base.Trainer` resolved from the run's framework,
so adding a new library never touches this file.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from celery import shared_task  # type: ignore
except Exception:  # pragma: no cover - fallback when Celery not installed

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


@shared_task(name="app.jobs.tasks.training.train_task")
def train_task(payload: dict) -> dict:
    job_id = payload.get("jobId")
    experiment_id = payload.get("experimentId")
    db = _make_session()
    error_msg: str | None = None
    result: dict = {}

    try:
        from app.models.annotation import Annotation
        from app.models.artifact import ModelArtifact
        from app.models.asset import Asset
        from app.models.dataset import ClassMap, Dataset
        from app.models.dataset_version import DatasetVersion
        from app.models.experiment import ExperimentRun
        from app.services import training as training_pkg
        from app.services.jobs_service import update_job_status
        from app.services.storage import ensure_bucket, get_minio_client
        from app.services.training.base import TrainContext

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.05)

        run: ExperimentRun | None = db.get(ExperimentRun, experiment_id) if experiment_id else None
        if run is None:
            raise ValueError(f"ExperimentRun {experiment_id!r} not found")

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()

        params: dict = json.loads(run.params_json or "{}") if run.params_json else {}
        task_type = params.get("task", "detect")
        framework = (
            params.get("framework")
            or getattr(run, "framework", None)
            or training_pkg.registry.DEFAULT_FRAMEWORK
        )

        # Resolve assets / class names / annotations for the version.
        version_id = run.dataset_version_id
        assets: list[Asset] = []
        class_names: list[str] = []
        annotations_by_asset: dict[str, list[Annotation]] = {}
        if version_id:
            assets = db.query(Asset).filter(Asset.version_id == version_id).all()
            version: DatasetVersion | None = db.get(DatasetVersion, version_id)
            dataset: Dataset | None = db.get(Dataset, version.dataset_id) if version else None
            if dataset and dataset.class_map_id:
                cm: ClassMap | None = db.get(ClassMap, dataset.class_map_id)
                if cm:
                    raw = json.loads(cm.classes)
                    if raw and isinstance(raw[0], dict):
                        class_names = [c["name"] for c in raw]
                    else:
                        class_names = [str(c) for c in raw]
            asset_ids = [a.id for a in assets]
            if asset_ids:
                ann_rows = db.query(Annotation).filter(Annotation.asset_id.in_(asset_ids)).all()
                for ann in ann_rows:
                    annotations_by_asset.setdefault(ann.asset_id, []).append(ann)
            if not class_names:
                seen: list[str] = []
                for ann_list in annotations_by_asset.values():
                    for ann in ann_list:
                        if ann.class_name and ann.class_name not in seen:
                            seen.append(ann.class_name)
                class_names = seen or ["object"]

        # Resolve the train/val/test split for every asset (honor persisted
        # split; fall back to deterministic hash split).
        from app.services.split_service import (
            DEFAULT_SEED,
            asset_split,
            normalize_ratios,
            resolve_split,
        )

        ratios = normalize_ratios(
            params.get("split_train", 0.8),
            params.get("split_val", 0.2),
            params.get("split_test", 0.0),
        )
        split_seed = int(params.get("split_seed", DEFAULT_SEED))
        splits: dict[str, str] = {}
        split_counts = {"train": 0, "val": 0, "test": 0}
        for a in assets:
            s = asset_split(a) or resolve_split(a.id, ratios, split_seed)
            splits[a.id] = s
            split_counts[s] = split_counts.get(s, 0) + 1

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.1)

        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        minio_client = None
        if os.getenv("MINIO_DISABLED", "false").lower() != "true":
            try:
                minio_client = get_minio_client()
                ensure_bucket(minio_client, bucket)
            except Exception:
                minio_client = None

        # Single metrics blob persisted throughout: per-epoch history, the
        # resolved split, a final summary, and links to generated plots.
        epoch_metrics: list[dict] = []
        metrics_blob: dict[str, Any] = {
            "framework": framework,
            "epochs": epoch_metrics,
            "split": {
                "counts": split_counts,
                "ratios": {"train": ratios[0], "val": ratios[1], "test": ratios[2]},
                "seed": split_seed,
            },
        }
        run.metrics_json = json.dumps(metrics_blob)
        db.add(run)
        db.commit()

        def report(progress: float | None = None, epoch: dict | None = None) -> None:
            """Uniform progress/metrics callback handed to every trainer."""
            if epoch is not None:
                epoch_metrics.append(epoch)
                try:
                    run.metrics_json = json.dumps(metrics_blob)
                    db.add(run)
                    db.commit()
                except Exception:
                    pass
            if progress is not None and job_id:
                try:
                    update_job_status(db, job_id, status="running", progress=progress)
                except Exception:
                    pass

        minio_key: str | None = None
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            ctx = TrainContext(
                db=db,
                run=run,
                params=params,
                task=task_type,
                class_names=class_names,
                assets=assets,
                annotations_by_asset=annotations_by_asset,
                splits=splits,
                minio_client=minio_client,
                bucket=bucket,
                work_dir=work_dir,
                report=report,
            )

            try:
                trainer = training_pkg.get_trainer(framework)
                train_result = trainer.run(ctx)
            except ImportError as imp_err:
                # ML wheel for this framework missing in the worker image —
                # record a clean skip rather than crashing (mirrors prior behavior).
                epoch_metrics.append({"epoch": 0, "note": f"{framework} not available: {imp_err}"})
                run.metrics_json = json.dumps(metrics_blob)
                db.add(run)
                db.commit()
                train_result = None

            best_pt_path = train_result.best_model_path if train_result else None

            # Persist the trained model artifact.
            if best_pt_path and minio_client:
                try:
                    minio_key = f"models/{experiment_id}/best.pt"
                    minio_client.fput_object(bucket, minio_key, str(best_pt_path))
                    size_bytes = best_pt_path.stat().st_size
                    checksum = hashlib.md5(best_pt_path.read_bytes()).hexdigest()
                    artifact = ModelArtifact(
                        id=str(uuid.uuid4()),
                        project_id=run.project_id,
                        run_id=run.id,
                        version=1,
                        type="pytorch",
                        format="pytorch",
                        framework=framework,
                        storage_path=minio_key,
                        checksum=checksum,
                        size_bytes=size_bytes,
                    )
                    db.add(artifact)
                    db.commit()
                    db.refresh(artifact)
                    artifacts_data = json.loads(run.artifacts or "[]")
                    entry = {
                        "id": artifact.id,
                        "type": "pytorch",
                        "key": minio_key,
                        "framework": framework,
                    }
                    if train_result and train_result.artifact_meta:
                        entry["config"] = train_result.artifact_meta
                    artifacts_data.append(entry)
                    run.artifacts = json.dumps(artifacts_data)
                    db.add(run)
                    db.commit()
                except Exception as upload_err:
                    epoch_metrics.append({"warning": f"model upload failed: {upload_err}"})

            # Persist generated plots.
            plot_records: list[dict] = []
            if minio_client and train_result and train_result.plot_files:
                from app.services import storage as _storage

                for fpath in train_result.plot_files:
                    if not Path(fpath).exists():
                        continue
                    try:
                        ext = Path(fpath).suffix.lstrip(".").lower()
                        ctype = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
                        key = f"models/{experiment_id}/plots/{Path(fpath).name}"
                        _storage.put_bytes(
                            minio_client,
                            key,
                            Path(fpath).read_bytes(),
                            content_type=ctype,
                            bucket=bucket,
                        )
                        plot_records.append(
                            {"name": Path(fpath).stem, "file": Path(fpath).name, "key": key}
                        )
                    except Exception:
                        continue
            metrics_blob["plots"] = plot_records
            if train_result and train_result.final_metrics:
                metrics_blob["summary"] = train_result.final_metrics
            elif epoch_metrics:
                metrics_blob["summary"] = {
                    k: v for k, v in epoch_metrics[-1].items() if k != "epoch"
                }
            try:
                run.metrics_json = json.dumps(metrics_blob)
                db.add(run)
                db.commit()
            except Exception:
                pass

            if job_id:
                update_job_status(db, job_id, status="running", progress=0.97)

        run.status = "succeeded"
        run.completed_at = datetime.now(timezone.utc)
        if not run.metrics_json:
            run.metrics_json = json.dumps({"epochs": epoch_metrics})
        db.add(run)
        db.commit()

        if job_id:
            update_job_status(db, job_id, status="succeeded", progress=1.0)

        result = {
            "status": "succeeded",
            "experiment_id": experiment_id,
            "framework": framework,
            "epochs_completed": len(epoch_metrics),
            "model_key": minio_key,
        }

    except Exception as exc:
        error_msg = str(exc)
        result = {"status": "failed", "error": error_msg}
        try:
            if experiment_id:
                run_obj = db.get(ExperimentRun, experiment_id) if "ExperimentRun" in dir() else None
                if run_obj:
                    run_obj.status = "failed"
                    run_obj.completed_at = datetime.now(timezone.utc)
                    run_obj.metrics_json = json.dumps({"error": error_msg})
                    db.add(run_obj)
                    db.commit()
        except Exception:
            pass
        try:
            if job_id:
                from app.services.jobs_service import update_job_status

                update_job_status(db, job_id, status="failed", progress=0.0)
        except Exception:
            pass
    finally:
        db.close()

    return result
