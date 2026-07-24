"""Settings → Questions panel for the project question library."""

from __future__ import annotations

import streamlit as st

from transcriptx.core.analysis.llm_custom_qa.request_questions import (
    structured_library_from_settings,
)
from transcriptx.core.analysis.llm_custom_qa.resolve import normalize_library_questions
from transcriptx.core.config.persistence import patch_project_config_keys
from transcriptx.core.utils.config import get_config

_EVIDENCE_PACK_OPTIONS = [
    "interactions",
    "summary",
    "highlights",
    "llm_action_items",
    "topic_shift",
    "sentiment",
    "emotion",
    "moments",
    "insights",
]


def render_questions_panel() -> None:
    """Per-question editors + evidence catalog toggles."""
    st.subheader("Question library")
    st.caption(
        "Reusable questions for Custom Questions (`llm_custom_qa`). "
        "Each question can run globally and/or per named speaker. "
        "Saved to project config under `CONFIG_DIR` "
        "(Docker: `HOST_CONFIG_DIR` → `/data/.transcriptx`)."
    )
    cfg = get_config().analysis.llm_custom_qa
    saved = structured_library_from_settings(cfg)

    if "settings_qa_rows" not in st.session_state:
        st.session_state["settings_qa_rows"] = [
            {
                "text": q["text"],
                "global": bool(q["scopes"].get("global")),
                "per_speaker": bool(q["scopes"].get("per_speaker")),
            }
            for q in saved
        ] or [{"text": "", "global": True, "per_speaker": False}]

    rows = st.session_state["settings_qa_rows"]
    to_remove: list[int] = []
    for i, row in enumerate(rows):
        c1, c2, c3, c4 = st.columns([6, 1.2, 1.5, 0.8])
        with c1:
            row["text"] = st.text_input(
                f"Question {i + 1}",
                value=row.get("text") or "",
                key=f"settings_qa_text_{i}",
                label_visibility="collapsed",
                placeholder="Question text",
            )
        with c2:
            row["global"] = st.checkbox(
                "Global",
                value=bool(row.get("global", True)),
                key=f"settings_qa_global_{i}",
            )
        with c3:
            row["per_speaker"] = st.checkbox(
                "Per speaker",
                value=bool(row.get("per_speaker", False)),
                key=f"settings_qa_ps_{i}",
            )
        with c4:
            if st.button("✕", key=f"settings_qa_rm_{i}"):
                to_remove.append(i)
    for i in reversed(to_remove):
        rows.pop(i)
    if st.button("Add question", key="settings_qa_add"):
        rows.append({"text": "", "global": True, "per_speaker": False})

    st.markdown("#### Evidence catalog")
    include_transcript = st.checkbox(
        "Include transcript",
        value=bool(getattr(cfg, "include_transcript", True)),
        key="settings_qa_include_transcript",
    )
    routing_enabled = st.checkbox(
        "Enable evidence routing",
        value=bool(getattr(cfg, "routing_enabled", True)),
        key="settings_qa_routing",
    )
    current_packs = getattr(cfg, "evidence_pack_ids", None)
    use_all = current_packs is None
    all_packs = st.checkbox(
        "All current catalog packs (default)",
        value=use_all,
        key="settings_qa_all_packs",
    )
    selected_packs: list[str] = []
    if not all_packs:
        default_sel = list(current_packs) if isinstance(current_packs, list) else []
        selected_packs = st.multiselect(
            "Enabled packs",
            options=_EVIDENCE_PACK_OPTIONS,
            default=[p for p in default_sel if p in _EVIDENCE_PACK_OPTIONS],
            key="settings_qa_packs",
        )

    st.caption(
        f"Limits: {cfg.max_library_questions} questions, "
        f"{cfg.max_library_total_question_chars} total chars, "
        f"{cfg.max_question_chars} chars each."
    )
    if st.button("Save library", type="primary", key="settings_questions_save"):
        payload = []
        for row in rows:
            text = (row.get("text") or "").strip()
            if not text:
                continue
            g = bool(row.get("global"))
            ps = bool(row.get("per_speaker"))
            if not g and not ps:
                st.error(f"Question needs at least one scope: {text[:40]}")
                return
            payload.append({"text": text, "scopes": {"global": g, "per_speaker": ps}})
        try:
            normalised = normalize_library_questions(payload, settings=cfg)
        except Exception as exc:
            st.error(f"Invalid library: {exc}")
            return
        pack_ids = None if all_packs else list(selected_packs)
        patch_project_config_keys(
            {
                "analysis": {
                    "llm_custom_qa": {
                        "saved_questions": list(normalised),
                        "evidence_pack_ids": pack_ids,
                        "include_transcript": include_transcript,
                        "routing_enabled": routing_enabled,
                    }
                }
            }
        )
        cfg.saved_questions = list(normalised)
        cfg.evidence_pack_ids = pack_ids
        cfg.include_transcript = include_transcript
        cfg.routing_enabled = routing_enabled
        st.session_state["settings_qa_rows"] = [
            {
                "text": q["text"],
                "global": bool(q["scopes"]["global"]),
                "per_speaker": bool(q["scopes"]["per_speaker"]),
            }
            for q in normalised
        ] or [{"text": "", "global": True, "per_speaker": False}]
        st.success(f"Saved {len(normalised)} question(s).")
        st.rerun()
