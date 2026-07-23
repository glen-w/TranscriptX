"""Shared presentation helpers for custom QA answers under summary/speakers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import streamlit as st

from transcriptx.core.analysis.llm_custom_qa.readers import (
    load_committed_custom_qa_payload,
)
from transcriptx.core.analysis.llm_custom_qa.versioning import V2_SCHEMA_ID
from transcriptx.web.blocks.implementations.insights_custom_qa import (
    _render_answer_card,
)


def _safe_load(run_root: Optional[Path]) -> Optional[dict[str, Any]]:
    if run_root is None:
        return None
    try:
        return load_committed_custom_qa_payload(Path(run_root))
    except Exception:
        return None


def render_global_custom_qa_under_summary(run_root: Optional[Path]) -> None:
    """Append global answers after the summary hero body (or as fallback)."""
    payload = _safe_load(run_root)
    if not payload:
        return
    schema_id = str(payload.get("schema_id") or "")
    if schema_id and schema_id not in (
        "transcriptx.llm_custom_qa.v1",
        V2_SCHEMA_ID,
    ):
        st.caption("Custom questions artifact schema unsupported for display.")
        return
    answers = [
        row
        for row in (payload.get("answers") or [])
        if isinstance(row, dict)
        and row.get("scope", "global") == "global"
    ]
    # v1 rows have no scope field — treat as global
    if not answers and schema_id.endswith(".v1"):
        answers = [r for r in (payload.get("answers") or []) if isinstance(r, dict)]
    if not answers:
        return
    st.markdown("#### Custom questions")
    for i, row in enumerate(answers):
        _render_answer_card(row, key_prefix=f"hero_qa_{i}")


def render_speaker_custom_qa(
    run_root: Optional[Path],
    *,
    speaker_key: str,
    key_prefix: str,
) -> None:
    payload = _safe_load(run_root)
    if not payload:
        return
    blocks = payload.get("speaker_answers") or []
    matched = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if str(block.get("speaker_key") or "") == str(speaker_key):
            matched.extend(
                [r for r in (block.get("answers") or []) if isinstance(r, dict)]
            )
    if not matched:
        return
    st.markdown("##### Custom questions")
    for i, row in enumerate(matched):
        _render_answer_card(row, key_prefix=f"{key_prefix}_qa_{i}")


def render_speaker_custom_qa_fallback(run_root: Optional[Path]) -> None:
    """When speaker summaries absent but speaker answers exist."""
    payload = _safe_load(run_root)
    if not payload:
        return
    blocks = payload.get("speaker_answers") or []
    if not blocks:
        return
    st.markdown("#### Custom questions by speaker")
    for bi, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        st.markdown(
            f"**{block.get('speaker') or block.get('speaker_key') or 'Speaker'}**"
        )
        for i, row in enumerate(block.get("answers") or []):
            if isinstance(row, dict):
                _render_answer_card(row, key_prefix=f"speaker_fallback_{bi}_{i}")
