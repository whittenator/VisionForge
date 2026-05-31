"""Unit tests for the pluggable training-backend registry + capabilities.

These exercise only the framework-agnostic surface, so they run without torch /
timm / ultralytics installed.
"""

import pytest

from app.services import training as training_pkg
from app.services.training.registry import UnknownFrameworkError


def test_builtin_frameworks_registered():
    keys = {t.key for t in training_pkg.list_frameworks()}
    assert {"ultralytics", "timm"}.issubset(keys)


def test_get_trainer_defaults_to_ultralytics_for_backcompat():
    # None / empty framework maps to ultralytics so pre-framework runs keep working.
    assert training_pkg.get_trainer(None).key == "ultralytics"
    assert training_pkg.get_trainer("").key == "ultralytics"


def test_get_trainer_unknown_raises():
    with pytest.raises(UnknownFrameworkError):
        training_pkg.get_trainer("does-not-exist")


def test_supported_tasks():
    assert "classify" in training_pkg.get_trainer("timm").supported_tasks
    assert training_pkg.get_trainer("timm").supported_tasks == {"classify"}
    assert "detect" in training_pkg.get_trainer("ultralytics").supported_tasks


def test_capabilities_serialize_to_plain_dict():
    for trainer in training_pkg.list_frameworks():
        caps = trainer.capabilities().to_dict()
        assert caps["key"] == trainer.key
        assert isinstance(caps["supported_tasks"], list)
        assert isinstance(caps["groups"], list) and caps["groups"]
        # Every field is a serializable FieldDef-shaped dict.
        for group in caps["groups"]:
            assert "title" in group and "fields" in group
            for field in group["fields"]:
                assert {"key", "label", "type", "default"} <= set(field)
        assert isinstance(caps["device_options"], list)


def test_timm_architecture_group_has_searchable_model_field():
    caps = training_pkg.get_trainer("timm").capabilities().to_dict()
    arch = next(g for g in caps["groups"] if g["title"] == "Architecture")
    model_field = next(f for f in arch["fields"] if f["key"] == "model")
    assert model_field["type"] == "model"  # searchable backbone picker


def test_list_models_filters_by_query_for_ultralytics():
    ul = training_pkg.get_trainer("ultralytics")
    assert ul.list_models("detect", "yolov8n") == ["yolov8n.pt"]
    assert set(ul.list_models("classify")) == {f"yolov8{s}-cls.pt" for s in "nsmlx"}
