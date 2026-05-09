"""Unit tests for the metrics computations in the evaluation Celery task."""

from app.jobs.tasks.evaluation import (
    compute_classification_metrics,
    compute_detection_metrics,
)


def test_classification_perfect_prediction():
    pairs = [("cat", "cat"), ("dog", "dog"), ("cat", "cat")]
    out = compute_classification_metrics(pairs, ["cat", "dog"])
    assert out["metrics"]["accuracy"] == 1.0
    assert out["per_class"]["cat"]["precision"] == 1.0
    assert out["per_class"]["cat"]["recall"] == 1.0
    assert out["confusion"][0][0] == 2  # cat,cat
    assert out["confusion"][1][1] == 1  # dog,dog


def test_classification_with_errors():
    pairs = [
        ("cat", "cat"),
        ("dog", "cat"),  # FP for dog, FN for cat
        ("dog", "dog"),
        ("cat", "dog"),  # FP for cat, FN for dog
    ]
    out = compute_classification_metrics(pairs, ["cat", "dog"])
    assert out["metrics"]["accuracy"] == 0.5
    assert out["per_class"]["cat"]["support"] == 2
    assert out["per_class"]["dog"]["support"] == 2
    # confusion: row=gt, col=pred
    # cat,cat=1; cat,dog=1; dog,dog=1; dog,cat=1
    cm = out["confusion"]
    assert cm[0][0] == 1
    assert cm[0][1] == 1
    assert cm[1][0] == 1
    assert cm[1][1] == 1


def test_detection_perfect_match():
    items = [
        {
            "asset_id": "a",
            "gt": [{"class": "car", "bbox": (10, 10, 20, 20)}],
            "pred": [{"class": "car", "bbox": (10, 10, 20, 20), "score": 0.9}],
        }
    ]
    out = compute_detection_metrics(items, ["car"], iou_threshold=0.5)
    assert out["per_class"]["car"]["precision"] == 1.0
    assert out["per_class"]["car"]["recall"] == 1.0
    assert out["per_class"]["car"]["ap50"] > 0.9


def test_detection_misses_and_false_positives():
    items = [
        # 1 GT car, no pred → 1 FN
        {"asset_id": "a", "gt": [{"class": "car", "bbox": (0, 0, 10, 10)}], "pred": []},
        # 1 pred car with no GT → 1 FP
        {
            "asset_id": "b",
            "gt": [],
            "pred": [{"class": "car", "bbox": (0, 0, 10, 10), "score": 0.6}],
        },
        # match
        {
            "asset_id": "c",
            "gt": [{"class": "car", "bbox": (5, 5, 10, 10)}],
            "pred": [{"class": "car", "bbox": (5, 5, 10, 10), "score": 0.8}],
        },
    ]
    out = compute_detection_metrics(items, ["car"], iou_threshold=0.5)
    pc = out["per_class"]["car"]
    # 1 TP, 1 FP, 1 FN
    assert pc["precision"] == 0.5
    assert pc["recall"] == 0.5
    assert 0.0 < pc["ap50"] < 1.0


def test_detection_iou_below_threshold_is_fp():
    # GT and pred barely overlap
    items = [
        {
            "asset_id": "a",
            "gt": [{"class": "car", "bbox": (0, 0, 10, 10)}],
            "pred": [{"class": "car", "bbox": (8, 8, 10, 10), "score": 0.7}],
        }
    ]
    out = compute_detection_metrics(items, ["car"], iou_threshold=0.5)
    pc = out["per_class"]["car"]
    # Pred doesn't match → FP and FN (no match)
    assert pc["precision"] == 0.0
    assert pc["recall"] == 0.0


def test_detection_confusion_records_cross_class_match():
    """Wrong-class predictions that match a GT by IoU must populate off-diagonal."""
    items = [
        {
            "asset_id": "a",
            "gt": [{"class": "car", "bbox": (0, 0, 10, 10)}],
            "pred": [{"class": "truck", "bbox": (0, 0, 10, 10), "score": 0.9}],
        }
    ]
    out = compute_detection_metrics(items, ["car", "truck"], iou_threshold=0.5)
    cm = out["confusion"]
    # rows = GT, cols = pred. GT was car (idx 0), pred was truck (idx 1).
    assert cm[0][1] == 1
    assert cm[0][0] == 0
    # Class-strict pass: it's still an FP for truck and an FN for car.
    assert out["per_class"]["car"]["recall"] == 0.0
    assert out["per_class"]["truck"]["precision"] == 0.0
