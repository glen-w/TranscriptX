"""Run Analysis / Batch picker for custom questions."""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st

from transcriptx.core.analysis.llm_custom_qa.question_identity import (
    upsert_library_question,
)
from transcriptx.core.analysis.llm_custom_qa.request_questions import (
    structured_library_from_settings,
)
from transcriptx.core.analysis.llm_custom_qa.resolve import (
    EffectiveCustomQAQuestions,
    resolve_effective_custom_qa_questions,
)
from transcriptx.core.config.persistence import patch_project_config_keys
from transcriptx.core.utils.config import get_config


def render_custom_qa_picker(
    *,
    key_prefix: str,
    module_selected: bool,
) -> tuple[Optional[list[dict[str, Any]]], Optional[EffectiveCustomQAQuestions]]:
    """Render structured question picker.

    Returns ``(request_questions, effective)`` where request_questions is
    structured list / None / [].
    """
    if not module_selected:
        return None, None

    cfg = get_config().analysis.llm_custom_qa
    saved = structured_library_from_settings(cfg)
    max_per_run = int(getattr(cfg, "max_questions_per_run", 8))

    st.markdown("#### Custom questions")
    st.caption(
        "Select library questions and/or add ad-hoc rows. "
        "Scopes: Global and/or Per speaker."
    )

    labels = [
        f"{q['text'][:80]} [{'G' if q['scopes'].get('global') else ''}"
        f"{'S' if q['scopes'].get('per_speaker') else ''}]"
        for q in saved
    ]
    label_to_q = {labels[i]: saved[i] for i in range(len(saved))}

    selected_labels: list[str] = []
    if saved:
        selected_labels = st.multiselect(
            "From library",
            options=labels,
            default=[],
            key=f"{key_prefix}_saved",
            max_selections=max_per_run,
        )
    else:
        st.caption("No saved questions yet — add some in Settings → Questions.")

    if f"{key_prefix}_adhoc_rows" not in st.session_state:
        st.session_state[f"{key_prefix}_adhoc_rows"] = []

    adhoc_rows: list[dict[str, Any]] = st.session_state[f"{key_prefix}_adhoc_rows"]
    remove_idx: list[int] = []
    for i, row in enumerate(adhoc_rows):
        c1, c2, c3, c4, c5 = st.columns([5, 1.2, 1.5, 1.5, 0.7])
        with c1:
            row["text"] = st.text_input(
                f"Ad-hoc {i + 1}",
                value=row.get("text") or "",
                key=f"{key_prefix}_adhoc_text_{i}",
                label_visibility="collapsed",
                placeholder="Ad-hoc question",
            )
        with c2:
            row["global"] = st.checkbox(
                "Global",
                value=bool(row.get("global", True)),
                key=f"{key_prefix}_adhoc_g_{i}",
            )
        with c3:
            row["per_speaker"] = st.checkbox(
                "Per speaker",
                value=bool(row.get("per_speaker", False)),
                key=f"{key_prefix}_adhoc_ps_{i}",
            )
        with c4:
            row["save"] = st.checkbox(
                "Save",
                value=bool(row.get("save", False)),
                key=f"{key_prefix}_adhoc_save_{i}",
            )
        with c5:
            if st.button("✕", key=f"{key_prefix}_adhoc_rm_{i}"):
                remove_idx.append(i)
    for i in reversed(remove_idx):
        adhoc_rows.pop(i)
    if st.button("Add ad-hoc question", key=f"{key_prefix}_adhoc_add"):
        adhoc_rows.append(
            {"text": "", "global": True, "per_speaker": False, "save": False}
        )

    explicit_empty = st.checkbox(
        "Run with no questions (empty Q success artifact)",
        value=False,
        key=f"{key_prefix}_explicit_empty",
    )

    if explicit_empty:
        effective = resolve_effective_custom_qa_questions(
            request_questions=[],
            request_field_present=True,
            settings=cfg,
        )
        st.session_state[f"{key_prefix}_save_for_later_payload"] = None
        return [], effective

    combined: list[dict[str, Any]] = []
    for lab in selected_labels:
        q = label_to_q[lab]
        combined.append(
            {"text": q["text"], "scopes": dict(q["scopes"])}
        )
    save_payload: list[dict[str, Any]] = []
    for row in adhoc_rows:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        g = bool(row.get("global"))
        ps = bool(row.get("per_speaker"))
        if not g and not ps:
            st.error(f"Ad-hoc question needs a scope: {text[:40]}")
            effective = resolve_effective_custom_qa_questions(
                request_questions=[],
                request_field_present=True,
                settings=cfg,
            )
            return [], effective
        entry = {"text": text, "scopes": {"global": g, "per_speaker": ps}}
        combined.append(entry)
        if row.get("save"):
            save_payload.append(entry)

    if not combined:
        effective = resolve_effective_custom_qa_questions(
            request_questions=None,
            request_field_present=False,
            settings=cfg,
        )
        st.session_state[f"{key_prefix}_save_for_later_payload"] = save_payload or None
        return None, effective

    try:
        effective = resolve_effective_custom_qa_questions(
            request_questions=combined,
            request_field_present=True,
            settings=cfg,
        )
    except Exception as exc:
        st.error(f"Invalid questions: {exc}")
        effective = resolve_effective_custom_qa_questions(
            request_questions=[],
            request_field_present=True,
            settings=cfg,
        )
        return [], effective

    st.session_state[f"{key_prefix}_save_for_later_payload"] = save_payload or None
    structured = [
        {"text": q.text, "scopes": q.scopes.as_dict()} for q in effective.structured
    ]
    return structured, effective


def maybe_save_questions_for_later(*, key_prefix: str) -> None:
    """Upsert checked ad-hoc questions into the library (scope union)."""
    payload = st.session_state.pop(f"{key_prefix}_save_for_later_payload", None)
    if not payload:
        return
    cfg = get_config().analysis.llm_custom_qa
    existing = structured_library_from_settings(cfg)
    merged = list(existing)
    try:
        for entry in payload:
            merged = upsert_library_question(
                merged,
                text=entry["text"],
                scopes=entry["scopes"],
                max_question_chars=int(cfg.max_question_chars),
                max_library_questions=int(cfg.max_library_questions),
                max_library_total_question_chars=int(
                    cfg.max_library_total_question_chars
                ),
            )
    except Exception as exc:
        st.warning(f"Could not save questions to library: {exc}")
        return
    patch_project_config_keys(
        {
            "analysis": {
                "llm_custom_qa": {
                    "saved_questions": merged,
                }
            }
        }
    )
    cfg.saved_questions = merged
    st.toast(f"Saved {len(payload)} question(s) to library")
