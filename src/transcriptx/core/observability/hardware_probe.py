"""Shared hardware probe for Theme E (performance & hardware guidance).

Returns a coarse, honest snapshot of *this process* — not host VRAM or
``nvidia-smi``. Docker analysis often has no GPU even when the host can run
CUDA STT; consumers must keep that distinction.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Literal, Optional

from transcriptx.core.observability.run_performance.schema import RuntimeFingerprint
from transcriptx.core.utils.config.main import get_install_profile

MemoryBand = Literal["low", "mid", "high", "very_high", "unknown"]
Acceleration = Literal["cpu", "cuda", "mps", "other"]
CpuClass = Literal["low", "mid", "high", "unknown"]

_FORCE_CPU_ENV = "TRANSCRIPTX_FORCE_CPU"

# RAM bands (GiB). Boundaries are inclusive on the upper side of each band.
_MEMORY_BANDS: tuple[tuple[float, MemoryBand], ...] = (
    (8.0, "low"),
    (16.0, "mid"),
    (32.0, "high"),
    (float("inf"), "very_high"),
)

_CPU_CLASS_BY_COUNT: tuple[tuple[int, CpuClass], ...] = (
    (4, "low"),
    (8, "mid"),
    (float("inf"), "high"),  # type: ignore[arg-type]
)

_cache_lock = threading.Lock()
_cached: Optional["HardwareSnapshot"] = None


@dataclass(frozen=True)
class HardwareSnapshot:
    """Coarse hardware snapshot for estimates and recommendations."""

    os_family: str
    arch: str
    python_version: str
    cpu_count: Optional[int]
    cpu_class: CpuClass
    memory_gib: Optional[float]
    memory_band: MemoryBand
    acceleration: Acceleration
    acceleration_reason: Optional[str]
    in_container: bool
    install_profile: Optional[str]
    force_cpu: bool

    def to_runtime_fingerprint(self) -> RuntimeFingerprint:
        return RuntimeFingerprint(
            os_family=self.os_family[:128],
            arch=self.arch[:128],
            python_version=self.python_version[:128],
            cpu_class=self.cpu_class,
            memory_band=self.memory_band,
            acceleration=self.acceleration,
        )


def memory_band_from_gib(gib: Optional[float]) -> MemoryBand:
    if gib is None or gib <= 0:
        return "unknown"
    for upper, band in _MEMORY_BANDS:
        if gib < upper:
            return band
    return "very_high"


def cpu_class_from_count(n: Optional[int]) -> CpuClass:
    if n is None or n <= 0:
        return "unknown"
    if n <= 4:
        return "low"
    if n <= 8:
        return "mid"
    return "high"


def _force_cpu_enabled() -> bool:
    raw = (os.environ.get(_FORCE_CPU_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def detect_in_container() -> bool:
    """Best-effort container detection (Docker / common cgroup layouts)."""
    try:
        if os.path.exists("/.dockerenv"):
            return True
    except OSError:
        pass
    try:
        with open("/proc/1/cgroup", "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
        if "docker" in text or "containerd" in text or "/lxc/" in text:
            return True
    except OSError:
        pass
    return False


def _read_meminfo_gib() -> Optional[float]:
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    # kB
                    kib = float(parts[1])
                    return kib / (1024.0 * 1024.0)
    except (OSError, IndexError, ValueError):
        return None
    return None


def _read_sysctl_mem_gib() -> Optional[float]:
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "hw.memsize"],
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        bytes_total = float(out.decode("utf-8", errors="ignore").strip())
        if bytes_total > 0:
            return bytes_total / (1024.0**3)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return None


def detect_memory_gib() -> Optional[float]:
    """Return total RAM in GiB, or None when unavailable."""
    try:
        import psutil

        total = float(psutil.virtual_memory().total)
        if total > 0:
            return total / (1024.0**3)
    except Exception:
        pass
    if sys.platform.startswith("linux"):
        return _read_meminfo_gib()
    if sys.platform == "darwin":
        return _read_sysctl_mem_gib()
    return None


def detect_acceleration(
    *,
    force_cpu: Optional[bool] = None,
) -> tuple[Acceleration, Optional[str]]:
    """Return (acceleration, reason). Honours TRANSCRIPTX_FORCE_CPU."""
    forced = _force_cpu_enabled() if force_cpu is None else bool(force_cpu)
    if forced:
        return "cpu", "TRANSCRIPTX_FORCE_CPU"
    try:
        import torch

        try:
            if torch.cuda.is_available():
                return "cuda", None
        except Exception:
            pass
        try:
            mps = getattr(torch.backends, "mps", None)
            if mps is not None and mps.is_available():
                return "mps", None
        except Exception:
            pass
        return "cpu", None
    except Exception as exc:
        return "cpu", f"torch_unavailable:{type(exc).__name__}"


def _os_family() -> str:
    sysname = platform.system() or "unknown"
    return sysname.lower()


def probe_hardware(*, use_cache: bool = True) -> HardwareSnapshot:
    """Probe this process. Cached; never raises into callers."""
    global _cached
    if use_cache:
        with _cache_lock:
            if _cached is not None:
                return _cached
    try:
        snap = _probe_uncached()
    except Exception:
        snap = HardwareSnapshot(
            os_family="unknown",
            arch=platform.machine() or "unknown",
            python_version=platform.python_version(),
            cpu_count=None,
            cpu_class="unknown",
            memory_gib=None,
            memory_band="unknown",
            acceleration="cpu",
            acceleration_reason="probe_failed",
            in_container=False,
            install_profile=None,
            force_cpu=_force_cpu_enabled(),
        )
    if use_cache:
        with _cache_lock:
            _cached = snap
    return snap


def _probe_uncached() -> HardwareSnapshot:
    force_cpu = _force_cpu_enabled()
    try:
        cpu_count = os.cpu_count()
    except Exception:
        cpu_count = None
    mem_gib = detect_memory_gib()
    accel, accel_reason = detect_acceleration(force_cpu=force_cpu)
    try:
        profile = get_install_profile()
    except Exception:
        profile = None
    return HardwareSnapshot(
        os_family=_os_family(),
        arch=(platform.machine() or "unknown").lower(),
        python_version=platform.python_version(),
        cpu_count=cpu_count,
        cpu_class=cpu_class_from_count(cpu_count),
        memory_gib=mem_gib,
        memory_band=memory_band_from_gib(mem_gib),
        acceleration=accel,
        acceleration_reason=accel_reason,
        in_container=detect_in_container(),
        install_profile=profile,
        force_cpu=force_cpu,
    )


def clear_hardware_probe_cache() -> None:
    """Test helper: drop the process-wide cache."""
    global _cached
    with _cache_lock:
        _cached = None
