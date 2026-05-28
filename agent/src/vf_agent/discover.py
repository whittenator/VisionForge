"""Hardware and OS discovery for the agent.

Produces the JSON payload returned by `GET /info` and used by the backend's
discovery endpoint to populate a Cluster row on registration.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from typing import Any


def _cpu_info() -> dict[str, Any]:
    try:
        import psutil  # type: ignore
    except ImportError:
        return {"cores": os.cpu_count() or 0, "usage_pct": 0.0}
    return {
        "cores": psutil.cpu_count(logical=True) or 0,
        "usage_pct": float(psutil.cpu_percent(interval=0.2)),
    }


def _ram_info() -> dict[str, Any]:
    try:
        import psutil  # type: ignore
    except ImportError:
        return {"total_mb": 0, "used_mb": 0}
    vm = psutil.virtual_memory()
    return {"total_mb": int(vm.total // (1024 * 1024)), "used_mb": int(vm.used // (1024 * 1024))}


def _disk_info() -> dict[str, Any]:
    # Report the root filesystem; this is what training output / model artifacts land on.
    path = os.getenv("VF_AGENT_DISK_PATH", "/")
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return {"total_gb": 0, "used_gb": 0, "path": path}
    return {
        "total_gb": int(usage.total // (1024**3)),
        "used_gb": int(usage.used // (1024**3)),
        "path": path,
    }


def _nvidia_gpus() -> list[dict[str, Any]] | None:
    try:
        import pynvml  # type: ignore
    except ImportError:
        return None
    try:
        pynvml.nvmlInit()
    except Exception:
        return None
    try:
        count = pynvml.nvmlDeviceGetCount()
    except Exception:
        return None
    gpus: list[dict[str, Any]] = []
    for i in range(count):
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            try:
                temp = float(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
            except Exception:
                temp = None
            gpus.append(
                {
                    "index": i,
                    "name": name,
                    "memory_mb": int(mem.total // (1024 * 1024)),
                    "mem_used_mb": int(mem.used // (1024 * 1024)),
                    "util_pct": float(util.gpu),
                    "temperature_c": temp,
                }
            )
        except Exception:
            continue
    try:
        pynvml.nvmlShutdown()
    except Exception:
        pass
    return gpus


def _rocm_gpus() -> list[dict[str, Any]] | None:
    rocm_smi = shutil.which("rocm-smi")
    if not rocm_smi:
        return None
    try:
        out = subprocess.run(
            [rocm_smi, "--showproductname", "--showmeminfo", "vram", "--showuse", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return None
    gpus: list[dict[str, Any]] = []
    for key, value in data.items():
        if not key.startswith("card"):
            continue
        try:
            idx = int(key.replace("card", ""))
        except ValueError:
            continue
        name = value.get("Card series") or value.get("Card model") or value.get("Card vendor")
        total = _to_int(value.get("VRAM Total Memory (B)"))
        used = _to_int(value.get("VRAM Total Used Memory (B)"))
        gpus.append(
            {
                "index": idx,
                "name": name,
                "memory_mb": int(total // (1024 * 1024)) if total else 0,
                "mem_used_mb": int(used // (1024 * 1024)) if used else 0,
                "util_pct": _to_float(value.get("GPU use (%)")),
                "temperature_c": _to_float(value.get("Temperature (Sensor edge) (C)")),
            }
        )
    return gpus or None


def _to_int(v: Any) -> int:
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return 0


def _to_float(v: Any) -> float:
    try:
        return float(str(v).rstrip("%"))
    except (TypeError, ValueError):
        return 0.0


def detect_gpus() -> tuple[str, list[dict[str, Any]]]:
    """Return `(vendor, gpus[])` where vendor is one of nvidia | rocm | cpu."""
    gpus = _nvidia_gpus()
    if gpus:
        return "nvidia", gpus
    gpus = _rocm_gpus()
    if gpus:
        return "rocm", gpus
    return "cpu", []


def _os_info() -> dict[str, Any]:
    return {
        "name": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "arch": platform.machine(),
        "python": platform.python_version(),
    }


def discover() -> dict[str, Any]:
    """Return a full hardware + OS snapshot for the backend discover endpoint."""
    vendor, gpus = detect_gpus()
    cpu = _cpu_info()
    ram = _ram_info()
    disk = _disk_info()
    return {
        "cpu_cores": cpu["cores"],
        "cpu_usage_pct": cpu["usage_pct"],
        "ram_total_mb": ram["total_mb"],
        "ram_used_mb": ram["used_mb"],
        "disk_total_gb": disk["total_gb"],
        "disk_used_gb": disk["used_gb"],
        "disk_path": disk["path"],
        "gpu_vendor": vendor,
        "gpu_count": len(gpus),
        "gpu_model": gpus[0]["name"] if gpus else None,
        "gpu_memory_mb": gpus[0]["memory_mb"] if gpus else 0,
        "gpu_usage_pct": (sum(g["util_pct"] for g in gpus) / len(gpus)) if gpus else 0.0,
        "gpus": gpus,
        "os": _os_info(),
    }


def main() -> None:
    print(json.dumps(discover(), indent=2))


if __name__ == "__main__":
    main()
