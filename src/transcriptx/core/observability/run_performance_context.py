"""Helpers to populate run_performance sidecar context (Theme E)."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from transcriptx.core.observability.hardware_probe import probe_hardware
from transcriptx.core.observability.run_estimate import workload_from_segments
from transcriptx.core.observability.run_performance.schema import (
    AnalysisContextSnapshot,
    RuntimeFingerprint,
    WorkloadSnapshot,
)


def build_runtime_fingerprint() -> RuntimeFingerprint:
    return probe_hardware().to_runtime_fingerprint()


def build_workload_from_canonical(canonical: Any) -> Optional[WorkloadSnapshot]:
    segments = getattr(canonical, "segments", None)
    if not isinstance(segments, list):
        return None
    return workload_from_segments(segments)


def build_analysis_context(
    *,
    app_version: Optional[str],
    requested_module_count: int,
    run_results: Optional[Mapping[str, Any]] = None,
    mode: Optional[str] = None,
    profile: Optional[str] = None,
    config_hash: Optional[str] = None,
) -> AnalysisContextSnapshot:
    """Fill AnalysisContextSnapshot; prefer values from committed run_results."""
    rr = run_results or {}
    preset = rr.get("analysis_preset")
    # Store preset under profile (schema has no analysis_preset field).
    resolved_profile = profile or (
        str(preset).strip().lower() if preset else None
    )
    resolved_mode = mode or (
        str(rr.get("mode")).strip().lower() if rr.get("mode") else None
    )
    return AnalysisContextSnapshot(
        mode=resolved_mode,
        profile=resolved_profile,
        config_hash=config_hash,
        app_version=app_version,
        requested_module_count=requested_module_count,
    )


def sum_workloads(parts: Sequence[WorkloadSnapshot]) -> WorkloadSnapshot:
    """Aggregate member workloads for a group sidecar."""
    dur = 0.0
    has_dur = False
    words = 0
    segs = 0
    speakers = 0
    for w in parts:
        if w.transcript_duration_s is not None:
            dur += float(w.transcript_duration_s)
            has_dur = True
        if w.word_count is not None:
            words += int(w.word_count)
        if w.segment_count is not None:
            segs += int(w.segment_count)
        if w.speaker_count is not None:
            speakers += int(w.speaker_count)
    return WorkloadSnapshot(
        transcript_duration_s=dur if has_dur else None,
        word_count=words,
        segment_count=segs,
        speaker_count=speakers,
    )
