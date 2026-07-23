"""Run Analysis / Batch picker for custom questions."""

from __future__ import annotations

import uuid
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

_SCOPE_OPTIONS = (
    "Global",
    "Per speaker",
    "Global + per speaker",
)


def _scope_label(global_: bool, per_speaker: bool) -> str:
    if global_ and per_speaker:
        return "Global + per speaker"
    if per_speaker:
        return "Per speaker"
    return "Global"


def _scope_from_label(label: str) -> tuple[bool, bool]:
    if label == "Per speaker":
        return False, True
    if label == "Global + per speaker":
        return True, True
    return True, False


def _new_row() -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "text": "",
        "global": True,
        "per_speaker": False,
    }


def _summary_scopes(questions: list[dict[str, Any]]) -> str:
    if not questions:
        return "None"
    any_g = any(q.get("scopes", {}).get("global") for q in questions)
    any_ps = any(q.get("scopes", {}).get("per_speaker") for q in questions)
    if any_g and any_ps:
        return "Global and per speaker"
    if any_ps:
        return "Per speaker"
    return "Global"


def _library_label(q: dict[str, Any]) -> str:
    return (
        f"{q['text'][:80]} [{'G' if q['scopes'].get('global') else ''}"
        f"{'S' if q['scopes'].get('per_speaker') else ''}]"
    )


def render_custom_qa_picker(
    *,
    key_prefix: str,
    always_show: bool = True,
    module_selected: bool | None = None,
) -> tuple[
    Optional[list[dict[str, Any]]],
    Optional[EffectiveCustomQAQuestions],
    bool,
]:
    """Render structured question picker.

    Returns ``(request_questions, effective, custom_qa_execution)``.

    ``custom_qa_execution`` is True when the module should run (questions or
    Advanced empty-artifact). False for Skip — strip ``llm_custom_qa``.

    ``module_selected`` is accepted for call-site compatibility and ignored;
    the section is always shown when ``always_show`` is True.
    """
    del module_selected
    if not always_show:
        return None, None, False

    cfg = get_config().analysis.llm_custom_qa
    saved = structured_library_from_settings(cfg)
    max_per_run = int(getattr(cfg, "max_questions_per_run", 8))

    rows_key = f"{key_prefix}_adhoc_rows"
    if rows_key not in st.session_state:
        st.session_state[rows_key] = []
    for row in st.session_state[rows_key]:
        if "id" not in row:
            row["id"] = str(uuid.uuid4())
        row.pop("save", None)

    skip_key = f"{key_prefix}_skip"
    empty_artifact_key = f"{key_prefix}_empty_artifact"
    saved_key = f"{key_prefix}_saved"

    header = st.empty()

    with st.expander("Edit questions", expanded=False):
        labels = [_library_label(q) for q in saved]
        label_to_q = {labels[i]: saved[i] for i in range(len(saved))}

        selected_labels: list[str] = []
        if saved:
            selected_labels = st.multiselect(
                "From library",
                options=labels,
                default=[],
                key=saved_key,
                max_selections=max_per_run,
            )
        else:
            st.caption("No saved questions yet — add some in Settings → Questions.")
            selected_labels = []

        adhoc_rows: list[dict[str, Any]] = st.session_state[rows_key]
        remove_ids: list[str] = []
        for row in adhoc_rows:
            rid = row["id"]
            c1, c2, c3, c4 = st.columns([5, 2.2, 1.6, 0.7])
            with c1:
                row["text"] = st.text_input(
                    "Question",
                    value=row.get("text") or "",
                    key=f"{key_prefix}_adhoc_text_{rid}",
                    label_visibility="collapsed",
                    placeholder="Describe the question…",
                )
            with c2:
                scope_label = _scope_label(
                    bool(row.get("global", True)),
                    bool(row.get("per_speaker", False)),
                )
                scope_key = f"{key_prefix}_adhoc_scope_{rid}"
                if scope_key not in st.session_state:
                    st.session_state[scope_key] = scope_label
                chosen = st.selectbox(
                    "Scope",
                    options=list(_SCOPE_OPTIONS),
                    key=scope_key,
                    label_visibility="collapsed",
                )
                g, ps = _scope_from_label(str(chosen))
                row["global"] = g
                row["per_speaker"] = ps
            with c3:
                if st.button(
                    "Save to library",
                    key=f"{key_prefix}_adhoc_save_{rid}",
                ):
                    _save_one_row_to_library(row, cfg=cfg)
            with c4:
                if st.button("✕", key=f"{key_prefix}_adhoc_rm_{rid}"):
                    remove_ids.append(rid)

        if remove_ids:
            st.session_state[rows_key] = [
                r for r in adhoc_rows if r.get("id") not in remove_ids
            ]
            st.rerun()

        if st.button("Add question", key=f"{key_prefix}_adhoc_add"):
            adhoc_rows.append(_new_row())
            st.rerun()

        combined = _collect_combined(selected_labels, label_to_q, adhoc_rows)
        has_active = bool(combined)

        if not has_active:
            st.checkbox(
                "Skip custom questions",
                value=True,
                key=skip_key,
                help=(
                    "Do not run the custom-questions module for this analysis. "
                    "No custom-questions artifact will be created."
                ),
            )
            with st.expander("Advanced", expanded=False):
                st.checkbox(
                    "Create an empty custom-questions result",
                    value=False,
                    key=empty_artifact_key,
                    help=(
                        "Run llm_custom_qa with zero questions and write an empty "
                        "success artifact. Distinct from Skip."
                    ),
                )
        else:
            st.session_state[skip_key] = False
            st.session_state[empty_artifact_key] = False

    # Re-read after widgets (session may hold library selection).
    selected_labels = list(st.session_state.get(saved_key) or [])
    label_to_q = {_library_label(q): q for q in saved}
    combined = _collect_combined(
        selected_labels, label_to_q, st.session_state.get(rows_key) or []
    )

    n = len(combined)
    if n == 0:
        header.markdown("#### Custom questions · None")
    else:
        header.markdown(
            f"#### Custom questions · {n} · {_summary_scopes(combined)}"
        )

    skip = bool(st.session_state.get(skip_key, True))
    empty_artifact = bool(st.session_state.get(empty_artifact_key, False))

    if empty_artifact and not combined:
        effective = resolve_effective_custom_qa_questions(
            request_questions=[],
            request_field_present=True,
            settings=cfg,
        )
        return [], effective, True

    if (skip and not combined) or not combined:
        return None, None, False

    try:
        effective = resolve_effective_custom_qa_questions(
            request_questions=combined,
            request_field_present=True,
            settings=cfg,
        )
    except Exception as exc:
        st.error(f"Invalid questions: {exc}")
        return [], None, False

    structured = [
        {"text": q.text, "scopes": q.scopes.as_dict()} for q in effective.structured
    ]
    return structured, effective, True


def _collect_combined(
    selected_labels: list[str],
    label_to_q: dict[str, dict[str, Any]],
    adhoc_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    for lab in selected_labels:
        q = label_to_q.get(lab)
        if q:
            combined.append({"text": q["text"], "scopes": dict(q["scopes"])})
    for row in adhoc_rows:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        g = bool(row.get("global"))
        ps = bool(row.get("per_speaker"))
        if not g and not ps:
            continue
        combined.append({"text": text, "scopes": {"global": g, "per_speaker": ps}})
    return combined


def _save_one_row_to_library(row: dict[str, Any], *, cfg: Any) -> None:
    text = (row.get("text") or "").strip()
    if not text:
        st.warning("Enter question text before saving.")
        return
    g = bool(row.get("global"))
    ps = bool(row.get("per_speaker"))
    if not g and not ps:
        st.warning("Choose a scope before saving.")
        return
    existing = structured_library_from_settings(cfg)
    before_n = len(existing)
    try:
        merged = upsert_library_question(
            existing,
            text=text,
            scopes={"global": g, "per_speaker": ps},
            max_question_chars=int(cfg.max_question_chars),
            max_library_questions=int(cfg.max_library_questions),
            max_library_total_question_chars=int(
                cfg.max_library_total_question_chars
            ),
        )
    except Exception as exc:
        st.warning(f"Could not save question to library: {exc}")
        return
    patch_project_config_keys(
        {"analysis": {"llm_custom_qa": {"saved_questions": merged}}}
    )
    cfg.saved_questions = merged
    if len(merged) == before_n:
        st.toast("Question already in library (scopes updated if needed)")
    else:
        st.toast("Saved question to library")


def maybe_save_questions_for_later(*, key_prefix: str) -> None:
    """No-op retained for call-site compatibility; saves are per-row now."""
    del key_prefix
