"""Core abstractions for pluggable training backends.

A :class:`Trainer` wraps one ML library (Ultralytics, Timm, …). It declares the
tasks it supports and a *capability descriptor* (the model catalogues and the
hyperparameter / augmentation form, expressed as serializable field
definitions). The same descriptor drives the frontend form, so adding a library
means implementing a ``Trainer`` and registering it — no frontend or
orchestration edits.

The Celery training task builds a :class:`TrainContext` (the minimal shared
surface every trainer needs: the dataset, the resolved split, MinIO access, a
scratch dir, and a uniform progress/metrics ``report`` callback) and calls
:meth:`Trainer.run`. Downstream stages (ONNX export, evaluation, inference)
resolve the trainer by ``key`` and call the relevant predict/export hook, so no
stage hard-codes a library name.
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class FieldDef:
    """One tunable knob, mirroring the frontend ``FieldDef`` shape.

    ``type`` is one of ``number | bool | select | text | model``. ``model`` is a
    searchable architecture picker backed by ``Trainer.list_models``.
    """

    key: str
    label: str
    type: str
    default: Any
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: list[str] | None = None
    help: str | None = None


@dataclass
class FieldGroup:
    """A titled, collapsible group of fields (e.g. "Optimizer & Schedule")."""

    title: str
    fields: list[FieldDef]


@dataclass
class Capabilities:
    """Everything the frontend needs to render a framework's training form."""

    key: str
    label: str
    supported_tasks: list[str]
    models_by_task: dict[str, list[str]]
    groups: list[FieldGroup]
    device_options: list[str]

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# Progress / metrics reporting callback. ``progress`` is a 0..1 fraction (or
# None to leave it unchanged); ``epoch`` is an optional per-epoch metrics entry
# that gets appended to the run's epoch history and persisted.
ReportFn = Callable[..., None]


@dataclass
class TrainContext:
    """The shared surface a trainer needs to execute one run.

    Everything framework-agnostic (DB session, the resolved dataset + split,
    object storage, a scratch directory, and the progress callback) lives here
    so each :class:`Trainer` only has to express the library-specific bits.
    """

    db: Any
    run: Any
    params: dict[str, Any]
    task: str
    class_names: list[str]
    assets: list[Any]
    annotations_by_asset: dict[str, list[Any]]
    splits: dict[str, str]
    minio_client: Any
    bucket: str
    work_dir: Path
    report: ReportFn


@dataclass
class TrainResult:
    """What a trainer hands back to the task for generic persistence."""

    best_model_path: Path | None = None
    final_metrics: dict[str, Any] = field(default_factory=dict)
    plot_files: list[Path] = field(default_factory=list)
    # Framework-specific reconstruction info (e.g. timm arch/config) stored
    # alongside the artifact so export/inference can rebuild the model.
    artifact_meta: dict[str, Any] = field(default_factory=dict)


class Predictor(Protocol):
    """Marker protocol; concrete predictors are framework-defined opaque objects."""


class Trainer(ABC):
    """Interface every training backend implements."""

    #: Stable identifier persisted on runs/artifacts (e.g. "ultralytics", "timm").
    key: str = ""
    #: Human-readable label shown in the UI.
    label: str = ""
    #: Tasks this backend can train (subset of detect|classify|segment|pose).
    supported_tasks: set[str] = set()

    # -- capability surface ---------------------------------------------------
    @abstractmethod
    def capabilities(self) -> Capabilities:
        """Return the model catalogues + form schema for this backend."""

    def list_models(self, task: str, query: str = "") -> list[str]:
        """Return model names for ``task`` filtered by ``query``.

        Defaults to the static catalogue from :meth:`capabilities`. Backends with
        huge catalogues (e.g. Timm) override this with a live, filtered search.
        """
        models = self.capabilities().models_by_task.get(task, [])
        q = query.strip().lower()
        return [m for m in models if q in m.lower()] if q else models

    # -- training -------------------------------------------------------------
    @abstractmethod
    def run(self, ctx: TrainContext) -> TrainResult:
        """Build the dataset, train, and return the best model + metrics."""

    # -- export ---------------------------------------------------------------
    def export_onnx(
        self,
        local_pt: Path,
        out_dir: Path,
        *,
        opset: int | None = None,
        dynamic: bool = True,
    ) -> Path | None:
        """Export a trained ``.pt`` to ONNX. Returns the path, or None on skip."""
        raise NotImplementedError(f"{self.key} does not support ONNX export")

    # -- inference / evaluation ----------------------------------------------
    def load_predictor(self, local_pt: Path) -> Any:
        """Load a trained model into a reusable predictor object."""
        raise NotImplementedError(f"{self.key} does not support inference")

    def predict_classification(self, predictor: Any, image_path: str) -> tuple[str, float]:
        """Return ``(class_name, score)`` for a single image."""
        raise NotImplementedError(f"{self.key} does not support classification inference")

    def predict_detections(
        self, predictor: Any, image_path: str, score_threshold: float
    ) -> list[dict[str, Any]]:
        """Return a list of ``{class, bbox, score}`` detections for one image."""
        raise NotImplementedError(f"{self.key} does not support detection inference")
