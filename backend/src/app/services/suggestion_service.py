"""AI-assisted annotation suggestions.

Resolves the model trained on an asset's dataset, runs inference on the image,
and returns predicted annotations *without persisting them*. The annotator
overlays these as proposals the user can accept, edit, or reject; accepted ones
are saved through the normal bulk-annotation path.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.artifact import ModelArtifact
from app.models.asset import Asset
from app.models.dataset_version import DatasetVersion
from app.models.experiment import ExperimentRun
from app.services import inference_service
from app.services.asset_fetch import fetch_asset_bytes


class SuggestionError(Exception):
    """Base error for the suggestion flow."""


class NoModelError(SuggestionError):
    """No successful model is available for the asset's dataset."""


@dataclass
class Suggestion:
    type: str  # "box" | "classification"
    geometry: dict
    class_name: str
    score: float


def candidate_artifacts_for_dataset(db: Session, dataset_id: str) -> list[ModelArtifact]:
    """All artifacts from successful runs on any version of this dataset, newest first.

    Drives the annotator's model-override dropdown.
    """
    rows = (
        db.execute(
            select(ModelArtifact)
            .join(ExperimentRun, ModelArtifact.run_id == ExperimentRun.id)
            .join(DatasetVersion, ExperimentRun.dataset_version_id == DatasetVersion.id)
            .where(
                DatasetVersion.dataset_id == dataset_id,
                ExperimentRun.status == "succeeded",
            )
            .order_by(ModelArtifact.created_at.desc())
        )
        .scalars()
        .all()
    )
    return list(rows)


def latest_artifact_for_dataset(db: Session, dataset_id: str) -> ModelArtifact | None:
    arts = candidate_artifacts_for_dataset(db, dataset_id)
    return arts[0] if arts else None


def suggest_annotations(
    db: Session,
    *,
    asset_id: str,
    artifact_id: str | None = None,
    score_threshold: float = 0.25,
) -> tuple[ModelArtifact, list[Suggestion]]:
    """Run a trained model on an asset and map detections to suggestions.

    Raises NoModelError when no usable artifact exists; SuggestionError for a
    missing asset or an artifact that does not belong to the asset's dataset.
    """
    asset = db.get(Asset, asset_id)
    if not asset:
        raise SuggestionError("asset not found")

    if artifact_id:
        artifact = db.get(ModelArtifact, artifact_id)
        if not artifact:
            raise NoModelError("requested model not found")
        # The override must be a model trained on this dataset.
        allowed = {a.id for a in candidate_artifacts_for_dataset(db, asset.dataset_id)}
        if artifact.id not in allowed:
            raise SuggestionError("model was not trained on this dataset")
    else:
        artifact = latest_artifact_for_dataset(db, asset.dataset_id)
        if not artifact:
            raise NoModelError("no successful model trained on this dataset")

    image_bytes = fetch_asset_bytes(asset)
    result = inference_service.predict(artifact, image_bytes, score_threshold=score_threshold)

    suggestions: list[Suggestion] = []
    for det in result.get("detections", []):
        bbox = det.get("bbox") or [0, 0, 0, 0]
        x, y, w, h = bbox
        suggestions.append(
            Suggestion(
                type="box",
                geometry={"x": x, "y": y, "w": w, "h": h},
                class_name=str(det.get("class", "")),
                score=float(det.get("score", 0.0)),
            )
        )
    cls = result.get("classification")
    if cls:
        suggestions.append(
            Suggestion(
                type="classification",
                geometry={"class": cls.get("class", "")},
                class_name=str(cls.get("class", "")),
                score=float(cls.get("score", 0.0)),
            )
        )
    return artifact, suggestions
