from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Any

import psutil


def _detect_llama_cpp_gpu_offload_support() -> bool | None:
    try:
        import llama_cpp as lc

        support_fn = getattr(lc, "llama_supports_gpu_offload", None)
        if callable(support_fn):
            return bool(support_fn())
    except Exception:
        return None
    return None


def _detect_nvidia_gpus() -> list[dict[str, str]]:
    if shutil.which("nvidia-smi") is None:
        return []

    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader",
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=2, check=False)
        if completed.returncode != 0:
            return []

        devices: list[dict[str, str]] = []
        for raw in completed.stdout.splitlines():
            line = raw.strip()
            if not line:
                continue
            parts = [item.strip() for item in line.split(",", maxsplit=1)]
            if len(parts) == 2:
                devices.append({"name": parts[0], "memory": parts[1]})
            else:
                devices.append({"name": line, "memory": "unknown"})
        return devices
    except Exception:
        return []


def probe_hardware_profile() -> dict[str, Any]:
    vm = psutil.virtual_memory()
    llama_gpu_support = _detect_llama_cpp_gpu_offload_support()
    nvidia_devices = _detect_nvidia_gpus()

    has_detected_gpu = bool(nvidia_devices)
    if llama_gpu_support is True and has_detected_gpu:
        recommended_profile = "gpu"
    elif llama_gpu_support is True:
        recommended_profile = "gpu-capable-no-device-detected"
    else:
        recommended_profile = "cpu-fast"

    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_physical_cores": psutil.cpu_count(logical=False) or 0,
        "cpu_logical_cores": psutil.cpu_count(logical=True) or 0,
        "ram_total_gb": round(vm.total / (1024**3), 2),
        "llama_cpp_gpu_offload_support": llama_gpu_support,
        "nvidia_devices": nvidia_devices,
        "recommended_profile": recommended_profile,
    }
