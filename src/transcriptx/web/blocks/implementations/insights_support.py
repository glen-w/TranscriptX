"""Shared Insights block helpers (loaders, transcript buttons, empty states)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.core.pipeline.manifest_loader import load_run_results
from transcriptx.core.pipeline.run_outcome_truth import project_canonical_outcomes
from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.components.module_run_prompt import render_module_required_hint
from transcriptx.web.navigation import (
    navigate_highlight_to_transcript,
    navigate_to_data_artifact,
)


def _loader(ctx: BlockContext):
    return ctx.services.content_loader


def _load_analysis_json(loader, module: str, suffix: str) -> Dict[str, Any] | None:
    """Prefer the Analysis-section cache so each artifact loads once per render."""
    from transcriptx.web.insights_presentation import load_cached_analysis_json

    if st.session_state.get("_insights_analysis_consolidating_provenance"):
        return load_cached_analysis_json(loader, module, suffix)
    if loader is None:
        return None
    try:
        payload = loader.load_json(module, suffix)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _module_failure_hint(run_root: Path, module_id: str) -> str | None:
    rr_path = run_root / "run_results.json"
    if not rr_path.exists():
        return None
    try:
        from transcriptx.core.analysis.llm_support.action_items_guidance import (
            format_module_failure_for_user,
        )

        run_results = load_run_results(rr_path)
        for row in project_canonical_outcomes(run_results):
            if row.module_id == module_id and row.status == "failed":
                return format_module_failure_for_user(
                    module_id=module_id,
                    error_message=row.reason,
                    error_code=row.error_code,
                )
    except Exception:
        return None
    return None


def _segment_index_from_refs(item: Dict[str, Any]) -> int | None:
    refs = item.get("segment_refs") or {}
    indexes = refs.get("segment_indexes") or []
    if indexes:
        try:
            return int(indexes[0])
        except (TypeError, ValueError):
            return None
    return None


def _render_open_in_transcript_button(
    *,
    session_slug: str | None,
    run_id: str | None,
    segment_index: int | None,
    start_time: float | None,
    quote: str | None,
    button_key: str,
) -> None:
    if not session_slug or not run_id or segment_index is None:
        return
    if st.button("Open in transcript", key=button_key, icon=ic.ARTICLE):
        navigate_highlight_to_transcript(
            session_slug=session_slug,
            run_id=run_id,
            segment_index=segment_index,
            start_time=start_time,
            highlight_query=(quote or "")[:120] or None,
        )


def _render_view_raw_file_link(
    ctx: BlockContext,
    module: str,
    suffix: str,
    *,
    link_key: str,
    storage_root: str | None = None,
    prefer_group_root: bool = False,
) -> None:
    if st.session_state.get("_insights_analysis_consolidating_provenance"):
        return
    loader = _loader(ctx)
    if loader is None:
        return
    artifact = loader.find_artifact(
        module,
        kind="data_json",
        suffix=suffix,
        storage_root=storage_root,
        prefer_group_root=prefer_group_root,
    )
    if artifact is None:
        artifact = loader.find_artifact(
            module,
            kind="data_txt",
            suffix=suffix.replace(".json", ".md"),
            storage_root=storage_root,
            prefer_group_root=prefer_group_root,
        )
    if artifact is None:
        return
    if st.button("View raw file", key=link_key, icon=ic.INVENTORY):
        navigate_to_data_artifact(artifact_id=artifact.id)


def _render_quiet_module_empty(
    *,
    label: str,
    run_root: Path | None,
    module: str,
    empty_hint: str,
    ctx: BlockContext,
    key: str,
) -> None:
    """User-facing empty/failed message with optional Technical details."""
    from transcriptx.web.run_health_presentation import module_outcome_state
    from transcriptx.web.summary_precedence import quiet_unavailable_message

    outcome = module_outcome_state(run_root, module) if run_root else "unknown"
    if outcome in {"failed", "skipped", "blocked"}:
        st.info(quiet_unavailable_message(label, outcome=outcome))
        hint = _module_failure_hint(run_root, module) if run_root else None
        if hint:
            # Guidance is the action; keep it visible, not buried.
            st.warning(hint)
        return
    render_module_required_hint(empty_hint, key=key, ctx=ctx)
