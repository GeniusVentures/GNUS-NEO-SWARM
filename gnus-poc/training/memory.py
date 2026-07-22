"""Pre-flight memory estimator for Apple Silicon training."""

import subprocess
import sys
from typing import Optional


_MIN_HEADROOM_GB = 2.0
_WARN_HEADROOM_GB = 10.0


def get_available_ram_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 ** 3)
    except ImportError:
        pass

    try:
        result = subprocess.run(["sysctl", "hw.memsize"], capture_output=True, text=True)
        if result.returncode == 0:
            total_bytes = int(result.stdout.strip().split()[-1])
            result = subprocess.run(["vm_stat"], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "free" in line.lower() and "pages" in line.lower():
                        free_pages = int(line.strip().split(":")[-1].strip().rstrip("."))
                        return (free_pages * 16384) / (1024 ** 3)
    except (subprocess.SubprocessError, ValueError, IndexError):
        pass

    return -1.0


def estimate_model_memory_gb(num_params_b: float, batch_size: int = 4, use_qlora: bool = True) -> float:
    if use_qlora:
        base_gb = num_params_b * 2 * 0.25
        adapter_gb = num_params_b * 0.02
        optimizer_gb = adapter_gb * 2
    else:
        base_gb = num_params_b * 2
        optimizer_gb = base_gb * 1.5
        adapter_gb = 0
    batch_gb = batch_size * 0.5
    return base_gb + optimizer_gb + batch_gb


def check_memory(num_params_b: float, batch_size: int = 4, use_qlora: bool = True) -> Optional[str]:
    available = get_available_ram_gb()
    if available < 0:
        return None

    estimated = estimate_model_memory_gb(num_params_b, batch_size, use_qlora)
    headroom = available - estimated

    if headroom < _MIN_HEADROOM_GB:
        return (
            f"MEMORY ERROR: Estimated {estimated:.1f}GB needed, "
            f"only {available:.1f}GB available ({headroom:.1f}GB headroom). "
            f"Reduce batch_size, enable qLoRA, or use a smaller model."
        )

    if headroom < _WARN_HEADROOM_GB:
        return (
            f"MEMORY WARNING: {headroom:.1f}GB headroom after estimated "
            f"{estimated:.1f}GB model. Training may be slow or OOM."
        )

    return None
