"""Unit tests for the agent hardware/OS discovery module.

These exercise the parsing helpers and the assembled ``discover()`` payload
shape. They are hermetic: GPU vendor libraries are optional and absent in CI,
so ``detect_gpus`` falls back to the CPU vendor.
"""

from __future__ import annotations

from vf_agent import discover


def test_to_int_parses_and_defaults():
    assert discover._to_int("42") == 42
    assert discover._to_int(7) == 7
    assert discover._to_int(None) == 0
    assert discover._to_int("not-a-number") == 0


def test_to_float_strips_percent_and_defaults():
    assert discover._to_float("55.5%") == 55.5
    assert discover._to_float("12") == 12.0
    assert discover._to_float(None) == 0.0
    assert discover._to_float("bad") == 0.0


def test_os_info_has_expected_keys():
    info = discover._os_info()
    assert {"name", "release", "version", "arch", "python"} <= set(info)
    assert isinstance(info["name"], str)


def test_detect_gpus_falls_back_to_cpu(monkeypatch):
    # Force both probes to report nothing so we land on the CPU vendor.
    monkeypatch.setattr(discover, "_nvidia_gpus", lambda: None)
    monkeypatch.setattr(discover, "_rocm_gpus", lambda: None)
    vendor, gpus = discover.detect_gpus()
    assert vendor == "cpu"
    assert gpus == []


def test_discover_payload_shape(monkeypatch):
    monkeypatch.setattr(discover, "_nvidia_gpus", lambda: None)
    monkeypatch.setattr(discover, "_rocm_gpus", lambda: None)
    snap = discover.discover()

    required = {
        "cpu_cores",
        "cpu_usage_pct",
        "ram_total_mb",
        "ram_used_mb",
        "disk_total_gb",
        "disk_used_gb",
        "gpu_vendor",
        "gpu_count",
        "gpu_model",
        "gpu_memory_mb",
        "gpu_usage_pct",
        "gpus",
        "os",
    }
    assert required <= set(snap)
    assert snap["gpu_vendor"] == "cpu"
    assert snap["gpu_count"] == len(snap["gpus"]) == 0
    assert isinstance(snap["cpu_cores"], int)


def test_discover_summarizes_gpu_list(monkeypatch):
    fake_gpus = [
        {"index": 0, "name": "RTX 4090", "memory_mb": 24576, "util_pct": 30.0},
        {"index": 1, "name": "RTX 4090", "memory_mb": 24576, "util_pct": 50.0},
    ]
    monkeypatch.setattr(discover, "_nvidia_gpus", lambda: fake_gpus)
    monkeypatch.setattr(discover, "_rocm_gpus", lambda: None)
    snap = discover.discover()
    assert snap["gpu_vendor"] == "nvidia"
    assert snap["gpu_count"] == 2
    assert snap["gpu_model"] == "RTX 4090"
    assert snap["gpu_memory_mb"] == 24576
    # Usage is the mean across GPUs.
    assert snap["gpu_usage_pct"] == 40.0
