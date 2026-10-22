"""Guidance-only analysis run-time estimates (Theme E).

Hybrid heuristic: published coefficients (seeded from performance envelopes)
blended with matching local ``run_performance.json`` priors when available.
Never used as a launch gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional, Sequence

from transcriptx.core.analysis.llm_support.model_selection import (
    LLM_MODEL_CONSUMER_ID_SET,
)
from transcriptx.core.observability.hardware_probe import (
    HardwareSnapshot,
    MemoryBand,
)
from transcriptx.core.observability.run_performance.schema import (
    RuntimeFingerprint,
    WorkloadSnapshot,
)

Confidence = Literal["heuristic", "calibrated", "low"]

_HEAVY_MODULES = frozenset(
    {
        "bertopic",
        "semantic_similarity",
        "contextual_emotion",
        "fine_grained_emotion",
        "voice",
        "chart_descriptions",
    }
)

# Baseline wall seconds for a ~30 min audio, Balanced, mid hardware, no LLM.
_BASE_WALL_S = 90.0
# Seconds of wall attributed per minute of audio (Balanced, mid HW).
_PER_AUDIO_MIN_S = 12.0
# Extra seconds per selected module (light modules).
_PER_MODULE_S = 4.0
# Extra for heavy / LLM modules.
_HEAVY_MODULE_S = 25.0
_LLM_MODULE_S = 20.0
_CHART_DESCRIPTIONS_S = 360.0  # often dominates Thorough

_PRESET_MULT = {
    "quick": 0.45,
    "balanced": 1.0,
    "thorough": 2.2,
    "custom": 1.1,
}

_MEMORY_MULT: dict[MemoryBand, float] = {
    "low": 1.55,
    "mid": 1.15,
    "high": 1.0,
    "very_high": 0.9,
    "unknown": 1.25,
}

_ACCEL_MULT = {
    "cuda": 0.75,
    "mps": 0.85,
    "cpu": 1.0,
    "other": 1.0,
}

_LLM_SIZE_MULT = {
    "tiny": 0.7,
    "small": 0.9,
    "mid": 1.0,
    "large": 1.45,
    "unknown": 1.1,
}

# Relative duration match for calibration (±40%).
_DURATION_MATCH_RATIO = 0.4


@dataclass(frozen=True)
class RunTimeEstimate:
    low_s: float
    high_s: float
    confidence: Confidence
    drivers: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()
    midpoint_s: float = 0.0

    def __post_init__(self) -> None:
        # dataclass frozen: use object.__setattr__
        mid = (float(self.low_s) + float(self.high_s)) / 2.0
        object.__setattr__(self, "midpoint_s", mid)


@dataclass(frozen=True)
class PriorRunTiming:
    """Minimal prior used for local calibration."""

    wall_clock_duration_ms: float
    transcript_duration_s: Optional[float] = None
    preset: Optional[str] = None
    memory_band: Optional[str] = None
    acceleration: Optional[str] = None
    requested_module_count: Optional[int] = None


def workload_from_segments(segments: Sequence[Mapping[str, Any]]) -> WorkloadSnapshot:
    """Build a WorkloadSnapshot from canonical segment dicts."""
    if not segments:
        return WorkloadSnapshot(
            transcript_duration_s=0.0,
            word_count=0,
            segment_count=0,
            speaker_count=0,
        )
    ends: list[float] = []
    speakers: set[str] = set()
    words = 0
    for seg in segments:
        try:
            end = seg.get("end")
            if end is not None:
                ends.append(float(end))
        except (TypeError, ValueError):
            pass
        sp = seg.get("speaker")
        if isinstance(sp, str) and sp.strip():
            speakers.add(sp.strip())
        wlist = seg.get("words")
        if isinstance(wlist, list) and wlist:
            words += len(wlist)
        else:
            text = seg.get("text") or ""
            if isinstance(text, str) and text.strip():
                words += len(text.split())
    duration = max(ends) if ends else None
    return WorkloadSnapshot(
        transcript_duration_s=duration,
        word_count=words,
        segment_count=len(segments),
        speaker_count=len(speakers),
    )


def _preset_key(preset: Optional[str]) -> str:
    key = (preset or "balanced").strip().lower()
    return key if key in _PRESET_MULT else "custom"


def _module_flags(module_ids: Sequence[str]) -> tuple[int, int, int, bool]:
    """Return (n_total, n_heavy, n_llm, has_chart_descriptions)."""
    n_heavy = 0
    n_llm = 0
    has_charts = False
    for mid in module_ids:
        name = (mid or "").strip()
        if not name:
            continue
        if name == "chart_descriptions":
            has_charts = True
            n_llm += 1
            continue
        if name in LLM_MODEL_CONSUMER_ID_SET:
            n_llm += 1
        elif name in _HEAVY_MODULES:
            n_heavy += 1
    return len([m for m in module_ids if m]), n_heavy, n_llm, has_charts


def _heuristic_midpoint_s(
    *,
    hardware: HardwareSnapshot,
    preset: Optional[str],
    module_ids: Sequence[str],
    workload: Optional[WorkloadSnapshot],
    llm_size_class: Optional[str],
    target_type: str,
    member_count: int,
) -> tuple[float, list[str]]:
    drivers: list[str] = []
    preset_k = _preset_key(preset)
    drivers.append(f"preset:{preset_k}")
    audio_s = None
    if workload is not None and workload.transcript_duration_s is not None:
        audio_s = float(workload.transcript_duration_s)
    audio_min = (audio_s / 60.0) if audio_s and audio_s > 0 else 15.0
    if audio_s is None:
        drivers.append("duration:assumed_15min")

    n_total, n_heavy, n_llm, has_charts = _module_flags(module_ids)
    mid = _BASE_WALL_S
    mid += audio_min * _PER_AUDIO_MIN_S
    mid += max(0, n_total - n_heavy - n_llm) * _PER_MODULE_S
    mid += n_heavy * _HEAVY_MODULE_S
    if n_llm:
        size_mult = _LLM_SIZE_MULT.get((llm_size_class or "unknown").lower(), 1.1)
        mid += n_llm * _LLM_MODULE_S * size_mult
        drivers.append(f"llm_modules:{n_llm}")
    if has_charts:
        mid += _CHART_DESCRIPTIONS_S * (
            0.6 if preset_k == "balanced" else 1.0 if preset_k == "thorough" else 0.3
        )
        drivers.append("chart_descriptions")

    mid *= _PRESET_MULT[preset_k]
    mid *= _MEMORY_MULT.get(hardware.memory_band, 1.25)
    mid *= _ACCEL_MULT.get(hardware.acceleration, 1.0)
    if hardware.install_profile == "core":
        mid *= 0.85
        drivers.append("install:core")
    elif hardware.install_profile == "full":
        drivers.append("install:full")

    if target_type == "group":
        # Members + aggregation overhead (envelopes: ~2.3× two-member sum).
        members = max(1, int(member_count))
        mid = mid * members * 1.15 + 120.0
        drivers.append(f"group_members:{members}")

    return max(30.0, mid), drivers


def _match_priors(
    priors: Sequence[PriorRunTiming],
    *,
    hardware: HardwareSnapshot,
    preset: Optional[str],
    workload: Optional[WorkloadSnapshot],
) -> list[float]:
    """Return wall seconds from priors that roughly match this machine/workload."""
    preset_k = _preset_key(preset)
    target_dur = None
    if workload is not None and workload.transcript_duration_s is not None:
        target_dur = float(workload.transcript_duration_s)
    matched: list[float] = []
    for prior in priors:
        if prior.wall_clock_duration_ms is None or prior.wall_clock_duration_ms <= 0:
            continue
        if prior.preset and _preset_key(prior.preset) != preset_k:
            continue
        if prior.memory_band and prior.memory_band != hardware.memory_band:
            continue
        if prior.acceleration and prior.acceleration != hardware.acceleration:
            continue
        if target_dur is not None and prior.transcript_duration_s:
            pd = float(prior.transcript_duration_s)
            if pd <= 0:
                continue
            ratio = abs(pd - target_dur) / max(target_dur, 1.0)
            if ratio > _DURATION_MATCH_RATIO:
                continue
        matched.append(float(prior.wall_clock_duration_ms) / 1000.0)
    return matched


def estimate_run_wall(
    *,
    hardware: HardwareSnapshot,
    preset: Optional[str],
    module_ids: Sequence[str],
    workload: Optional[WorkloadSnapshot] = None,
    llm_size_class: Optional[str] = None,
    target_type: str = "transcript",
    member_count: int = 1,
    priors: Optional[Sequence[PriorRunTiming]] = None,
) -> RunTimeEstimate:
    """Estimate wall-clock range. Guidance only — never blocks a run."""
    mid, drivers = _heuristic_midpoint_s(
        hardware=hardware,
        preset=preset,
        module_ids=module_ids,
        workload=workload,
        llm_size_class=llm_size_class,
        target_type=target_type,
        member_count=member_count,
    )
    caveats = [
        "Guidance, not a promise — first-run model downloads and Ollama "
        "contention can add many minutes.",
    ]
    if hardware.in_container:
        caveats.append(
            "Running in a container: acceleration reflects this process, "
            "not the host STT GPU."
        )
    if workload is None or workload.transcript_duration_s is None:
        caveats.append("Transcript duration unknown — range is wider.")

    matched = _match_priors(
        priors or (),
        hardware=hardware,
        preset=preset,
        workload=workload,
    )
    confidence: Confidence = "heuristic"
    if matched:
        prior_mid = sum(matched) / len(matched)
        # Blend 60% prior / 40% heuristic when calibrated.
        mid = 0.6 * prior_mid + 0.4 * mid
        confidence = "calibrated"
        drivers = list(drivers) + [f"local_priors:{len(matched)}"]
    elif workload is None or workload.transcript_duration_s is None:
        confidence = "low"

    # Spread: wider when low confidence.
    if confidence == "calibrated":
        spread = 0.25
    elif confidence == "low":
        spread = 0.55
    else:
        spread = 0.35
    low = max(20.0, mid * (1.0 - spread))
    high = mid * (1.0 + spread)
    return RunTimeEstimate(
        low_s=low,
        high_s=high,
        confidence=confidence,
        drivers=tuple(drivers),
        caveats=tuple(caveats),
    )


def format_duration_range(low_s: float, high_s: float) -> str:
    """Human range like ``about 8–15 min``."""

    def _parts(seconds: float) -> tuple[str, str]:
        """Return (value_text, unit) where unit is s|min|h."""
        s = max(0.0, float(seconds))
        if s < 90:
            return str(int(round(s))), "s"
        minutes = s / 60.0
        if minutes < 90:
            return str(max(1, int(round(minutes)))), "min"
        return f"{minutes / 60.0:.1f}", "h"

    low_v, low_u = _parts(low_s)
    high_v, high_u = _parts(high_s)
    if low_v == high_v and low_u == high_u:
        return f"about {low_v} {low_u}" if low_u != "s" else f"about {low_v}s"
    if low_u == high_u:
        if low_u == "s":
            return f"about {low_v}–{high_v}s"
        return f"about {low_v}–{high_v} {low_u}"
    # Mixed units (rare): keep both sides explicit.
    low_t = f"{low_v}s" if low_u == "s" else f"{low_v} {low_u}"
    high_t = f"{high_v}s" if high_u == "s" else f"{high_v} {high_u}"
    return f"about {low_t}–{high_t}"


def format_run_time_estimate(est: RunTimeEstimate) -> str:
    """One-line caption for Run Analysis / Batch."""
    rng = format_duration_range(est.low_s, est.high_s)
    conf = {
        "calibrated": "from similar runs on this machine",
        "heuristic": "heuristic",
        "low": "rough guess",
    }.get(est.confidence, "heuristic")
    return f"Estimated wall time: {rng} ({conf}). Guidance, not a promise."


def prior_from_sidecar(payload: Mapping[str, Any]) -> Optional[PriorRunTiming]:
    """Extract a PriorRunTiming from a loaded run_performance dict/model dump."""
    try:
        wall = float(payload.get("wall_clock_duration_ms") or 0)
    except (TypeError, ValueError):
        return None
    if wall <= 0:
        return None
    workload = payload.get("workload") or {}
    analysis = payload.get("analysis") or {}
    fp = payload.get("runtime_fingerprint") or {}
    dur = workload.get("transcript_duration_s") if isinstance(workload, Mapping) else None
    preset = None
    if isinstance(analysis, Mapping):
        preset = analysis.get("profile") or analysis.get("mode")
    return PriorRunTiming(
        wall_clock_duration_ms=wall,
        transcript_duration_s=float(dur) if dur is not None else None,
        preset=str(preset) if preset else None,
        memory_band=str(fp.get("memory_band")) if isinstance(fp, Mapping) else None,
        acceleration=str(fp.get("acceleration")) if isinstance(fp, Mapping) else None,
        requested_module_count=(
            int(analysis["requested_module_count"])
            if isinstance(analysis, Mapping)
            and analysis.get("requested_module_count") is not None
            else None
        ),
    )


def fingerprint_compatible(
    a: Optional[RuntimeFingerprint],
    b: HardwareSnapshot,
) -> bool:
    if a is None:
        return False
    if a.memory_band and a.memory_band != b.memory_band:
        return False
    if a.acceleration and a.acceleration != b.acceleration:
        return False
    return True
