"""Run Analysis / Batch captions for Theme E time estimates."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import streamlit as st

from transcriptx.core.analysis.llm_support.model_guidance import (
    infer_size_class,
    recommend_llm_for_hardware,
)
from transcriptx.core.analysis.llm_support.model_selection import LlmModelSelection
from transcriptx.core.observability.backend_recommend import analysis_model_hint
from transcriptx.core.observability.hardware_probe import probe_hardware
from transcriptx.core.observability.run_estimate import (
    PriorRunTiming,
    estimate_run_wall,
    format_run_time_estimate,
    prior_from_sidecar,
    workload_from_segments,
)
from transcriptx.core.observability.run_performance.schema import WorkloadSnapshot
from transcriptx.core.utils.paths import OUTPUTS_DIR


def _llm_size_from_selection(
    selection: Optional[LlmModelSelection],
    model_label: str,
) -> Optional[str]:
    if selection is not None and selection.shared_model:
        return infer_size_class(selection.shared_model)
    # Footer label may be a tag or a summary string — try infer.
    label = (model_label or "").strip()
    if label and " " not in label and label not in {"no LLM modules", "—"}:
        return infer_size_class(label)
    return None


def _workload_for_path(path: Optional[Path]) -> Optional[WorkloadSnapshot]:
    if path is None or not path.exists():
        return None
    try:
        from transcriptx.io.transcript_loader import load_segments

        segments = load_segments(str(path))
        return workload_from_segments(segments or [])
    except Exception:
        return None


def _sum_workloads(parts: Sequence[WorkloadSnapshot]) -> WorkloadSnapshot:
    from transcriptx.core.observability.run_performance_context import sum_workloads

    return sum_workloads(list(parts))


def _recent_priors(limit: int = 12) -> list[PriorRunTiming]:
    """Best-effort scan of recent sidecars under OUTPUTS_DIR."""
    root = Path(OUTPUTS_DIR)
    if not root.is_dir():
        return []
    priors: list[PriorRunTiming] = []
    try:
        # Prefer newest run dirs; cap filesystem work.
        candidates: list[Path] = []
        for child in root.iterdir():
            if not child.is_dir():
                continue
            # transcript runs: <stem>/<run_id>/
            for run_dir in child.iterdir() if child.is_dir() else []:
                if not run_dir.is_dir():
                    continue
                side = run_dir / ".transcriptx" / "run_performance.json"
                if side.is_file():
                    candidates.append(side)
                if len(candidates) >= 80:
                    break
            if len(candidates) >= 80:
                break
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        from transcriptx.core.observability.run_performance.io import (
            RunPerformanceLoadStatus,
            load_run_performance,
        )

        for path in candidates[:limit]:
            # path is …/<run_dir>/.transcriptx/run_performance.json
            run_dir = path.parent.parent
            loaded = load_run_performance(run_dir)
            if (
                loaded.status != RunPerformanceLoadStatus.ok
                or loaded.payload is None
            ):
                continue
            prior = prior_from_sidecar(loaded.payload.model_dump())
            if prior is not None:
                priors.append(prior)
    except Exception:
        return priors
    return priors


def render_run_time_guidance(
    *,
    preset: Optional[str],
    module_ids: Sequence[str],
    transcript_path: Optional[Path] = None,
    transcript_paths: Optional[Sequence[Path]] = None,
    target_type: str = "transcript",
    member_count: int = 1,
    llm_selection: Optional[LlmModelSelection] = None,
    model_label: str = "",
) -> None:
    """Caption under the Run Analysis / Batch footer. Never gates launch."""
    hardware = probe_hardware()
    workload: Optional[WorkloadSnapshot] = None
    if target_type == "batch" and transcript_paths:
        parts = []
        for p in list(transcript_paths)[:8]:
            w = _workload_for_path(Path(p))
            if w is not None:
                parts.append(w)
        if parts:
            workload = _sum_workloads(parts)
            # Scale estimate later via member_count for batch.
    elif transcript_path is not None:
        workload = _workload_for_path(Path(transcript_path))

    llm_size = _llm_size_from_selection(llm_selection, model_label)
    # Batch: treat as N independent transcripts roughly.
    effective_members = member_count
    if target_type == "batch" and transcript_paths:
        effective_members = max(1, len(transcript_paths))
        target_type = "group"

    est = estimate_run_wall(
        hardware=hardware,
        preset=preset,
        module_ids=list(module_ids),
        workload=workload,
        llm_size_class=llm_size,
        target_type=target_type,
        member_count=effective_members,
        priors=_recent_priors(),
    )
    st.caption(format_run_time_estimate(est))
    if est.caveats:
        # Keep one short secondary caveat.
        st.caption(est.caveats[0])

    hint = analysis_model_hint(hardware, preset=preset)
    if hint.prefer_light:
        st.caption(hint.message)


def render_llm_hardware_hint(installed: Sequence[str]) -> None:
    """One-line LLM size hint for compact setup / Settings."""
    hardware = probe_hardware()
    rec = recommend_llm_for_hardware(
        memory_band=hardware.memory_band,
        installed_models=installed,
    )
    st.caption(rec.caption)
