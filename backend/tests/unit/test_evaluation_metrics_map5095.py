"""Tests for the new mAP@[.5:.95] computation in compute_detection_metrics."""

from __future__ import annotations

from app.jobs.tasks.evaluation import (
    compute_detection_ap_at_iou,
    compute_detection_metrics,
)


def _items_perfect():
    """Predictions exactly match ground truth → AP at every IoU is 1."""
    items = []
    for i in range(3):
        gt = {"class": "cat", "bbox": (0.0, 0.0, 100.0, 100.0)}
        pred = {"class": "cat", "bbox": (0.0, 0.0, 100.0, 100.0), "score": 0.99}
        items.append({"asset_id": f"a{i}", "gt": [gt], "pred": [pred]})
    return items


def test_perfect_predictions_yield_full_map5095():
    items = _items_perfect()
    metrics = compute_detection_metrics(items, ["cat"], iou_threshold=0.5)
    m = metrics["metrics"]
    assert m["mAP50"] == 1.0
    assert m["mAP_5095"] == 1.0
    # All ten threshold buckets should be 1.0 too.
    for thr in (50, 55, 60, 65, 70, 75, 80, 85, 90, 95):
        assert m[f"mAP_{thr:02d}"] == 1.0, f"mAP_{thr:02d} = {m[f'mAP_{thr:02d}']}"


def test_loose_predictions_have_lower_map5095():
    """With ~54% IoU overlap, mAP@.5 stays high but mAP@[.5:.95] drops."""
    items = []
    for i in range(3):
        gt = {"class": "cat", "bbox": (0.0, 0.0, 100.0, 100.0)}
        # Shift by 30 pixels in x → IoU ≈ 0.538
        pred = {"class": "cat", "bbox": (30.0, 0.0, 100.0, 100.0), "score": 0.99}
        items.append({"asset_id": f"a{i}", "gt": [gt], "pred": [pred]})
    metrics = compute_detection_metrics(items, ["cat"], iou_threshold=0.5)
    m = metrics["metrics"]
    # The looser overlap is matched at IoU 0.50 only. The 11-point
    # interpolation pads each curve with a (recall=0, precision=1) anchor,
    # so unmatched thresholds produce ≈1/11 ≈ 0.091 — much lower than mAP_50.
    assert m["mAP_50"] >= 0.5
    assert m["mAP_75"] < 0.2
    assert m["mAP_95"] < 0.2
    assert m["mAP_5095"] < m["mAP_50"]


def test_compute_ap_helper_handles_empty():
    aps = compute_detection_ap_at_iou([], ["cat"], 0.5)
    assert aps == {"cat": 0.0}
