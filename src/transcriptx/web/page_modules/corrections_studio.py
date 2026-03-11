"""
Corrections Studio: DB-backed, resumable correction review in the browser.

Calls only CorrectionsStudioController (no direct service/repo imports).
"""

from __future__ import annotations

import os

import streamlit as st

from transcriptx.services.corrections_studio.controller import (
    CorrectionsStudioController,
)


@st.cache_data(ttl=120, show_spinner=False)
def _cached_corrections_studio_transcripts() -> list:
    return CorrectionsStudioController().list_transcripts()


def _render_progress_bar(stats: dict) -> None:
    total = sum(stats.values())
    if total == 0:
        st.caption("No candidates generated yet.")
        return
    pending = stats.get("pending", 0)
    accepted = stats.get("accepted", 0)
    rejected = stats.get("rejected", 0)
    skipped = stats.get("skipped", 0)
    done = accepted + rejected + skipped
    st.progress(done / total if total else 0)
    st.caption(
        f"**{pending}** pending | **{accepted}** accepted | "
        f"**{rejected}** rejected | **{skipped}** skipped | "
        f"**{total}** total"
    )


def _render_candidate_detail(
    controller: CorrectionsStudioController,
    session_id: str,
    candidate: dict,
) -> None:
    st.markdown(
        f"### {candidate['kind']} — confidence {candidate.get('confidence', 0):.2f}"
    )
    st.markdown(f"**{candidate['wrong_text']}** → **{candidate['suggested_text']}**")
    st.caption(f"Status: {candidate['status']} | ID: {candidate['id'][:8]}")

    diff = controller.get_candidate_local_diff(session_id, candidate["id"])

    # Process pending "Accept selected" from previous run
    pending = st.session_state.get("corrections_studio_pending_accept_selected")
    if pending and pending[0] == candidate["id"] and pending[1] == session_id:
        st.session_state.pop("corrections_studio_pending_accept_selected", None)
        keys = []
        for i, d in enumerate(diff.get("diffs") or []):
            if st.session_state.get(f"occ_sel_{candidate['id']}_{i}", True):
                sk = d.get("stable_occurrence_key")
                if sk:
                    keys.append(sk)
        controller.record_decision(
            session_id,
            candidate["id"],
            "accept",
            selected_occurrence_keys=keys if keys else None,
        )
        st.rerun()

    if diff.get("diffs"):
        with st.expander("Occurrences & Diffs", expanded=True):
            for i, d in enumerate(diff["diffs"]):
                speaker = d.get("speaker") or "?"
                time_info = ""
                if d.get("time_start") is not None:
                    time_info = f" ({d['time_start']:.1f}s–{d.get('time_end', 0):.1f}s)"
                row1, row2 = st.columns([1, 4])
                with row1:
                    st.checkbox(
                        "Apply",
                        value=True,
                        key=f"occ_sel_{candidate['id']}_{i}",
                        help="Apply this correction at this occurrence",
                    )
                with row2:
                    st.markdown(
                        f"**Segment {d.get('segment_index', '?')}** — {speaker}{time_info}"
                    )
                col_before, col_after = st.columns(2)
                with col_before:
                    st.text_area(
                        "Before",
                        value=d.get("before", ""),
                        height=80,
                        key=f"diff_before_{candidate['id']}_{i}",
                        disabled=True,
                    )
                with col_after:
                    st.text_area(
                        "After",
                        value=d.get("after", ""),
                        height=80,
                        key=f"diff_after_{candidate['id']}_{i}",
                        disabled=True,
                    )

    evidence = candidate.get("evidence_json")
    if evidence:
        with st.expander("Evidence"):
            st.json(evidence)

    st.divider()
    col_accept, col_accept_sel, col_reject, col_skip, col_learn = st.columns(5)
    with col_accept:
        if st.button("Accept all", key=f"accept_{candidate['id']}", type="primary"):
            controller.record_decision(session_id, candidate["id"], "accept")
            st.rerun()
    with col_accept_sel:
        if st.button("Accept selected", key=f"accept_sel_{candidate['id']}"):
            st.session_state["corrections_studio_pending_accept_selected"] = (
                candidate["id"],
                session_id,
            )
            st.rerun()
    with col_reject:
        if st.button("Reject", key=f"reject_{candidate['id']}"):
            controller.record_decision(session_id, candidate["id"], "reject")
            st.rerun()
    with col_skip:
        if st.button("Skip", key=f"skip_{candidate['id']}"):
            controller.record_decision(session_id, candidate["id"], "skip")
            st.rerun()
    with col_learn:
        if st.button("Accept & Learn Rule", key=f"learn_{candidate['id']}"):
            from transcriptx.core.corrections.models import CorrectionRule

            rule_hash = CorrectionRule.compute_id(
                candidate["kind"],
                [candidate["wrong_text"]],
                candidate["suggested_text"],
            )
            learn_params = {
                "rule_hash": rule_hash,
                "scope": "global",
                "rule_type": (
                    candidate["kind"]
                    if candidate["kind"] in ("token", "phrase", "acronym", "regex")
                    else "phrase"
                ),
                "wrong_variants_json": [candidate["wrong_text"]],
                "replacement_text": candidate["suggested_text"],
                "confidence": candidate.get("confidence", 0.5),
            }
            controller.record_decision(
                session_id,
                candidate["id"],
                "accept",
                learn_rule_params=learn_params,
            )
            st.rerun()


def render_corrections_studio() -> None:
    st.markdown(
        '<div class="main-header">Corrections Studio</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Review and apply transcript corrections. Select a transcript, review candidates, and export."
    )

    controller = CorrectionsStudioController()

    # Show one-time export success message if present
    export_success = st.session_state.pop("corrections_studio_export_success", None)
    if export_success:
        st.success(
            f"Exported to: {export_success['export_path']} "
            f"({export_success['applied_count']} corrections applied)"
        )

    # -- Transcript selection --
    transcripts = _cached_corrections_studio_transcripts()
    if not transcripts:
        st.info("No transcripts found. Add transcript JSON files to get started.")
        return

    options = [
        f"{t['base_name']} ({t.get('segment_count', 0)} segments)" for t in transcripts
    ]
    paths = [t["path"] for t in transcripts]
    idx = st.selectbox(
        "Transcript",
        range(len(options)),
        format_func=lambda i: options[i],
        key="corrections_studio_transcript",
    )
    transcript_path = paths[idx]

    # -- Start / Resume --
    col_start, col_regen = st.columns([1, 1])
    with col_start:
        start_clicked = st.button("Start / Resume Session", type="primary")
    with col_regen:
        regen_clicked = st.button("Regenerate Candidates")

    if start_clicked:
        try:
            session_data = controller.start_or_resume(transcript_path)
            st.session_state["corrections_studio_session_id"] = session_data["id"]
            st.session_state["corrections_studio_candidates_stale"] = session_data.get(
                "candidates_stale", False
            )
            candidates = controller.generate_candidates(session_data["id"])
            st.session_state["corrections_studio_active_candidate"] = None
            st.rerun()
        except Exception as e:
            st.error(f"Error starting session: {e}")
            return

    session_id = st.session_state.get("corrections_studio_session_id")
    if not session_id:
        st.info("Click **Start / Resume Session** to begin.")
        return

    # Ensure stale flag is set when resuming (e.g. returning to page with existing session)
    if "corrections_studio_candidates_stale" not in st.session_state:
        session_info = controller.get_session(session_id)
        st.session_state["corrections_studio_candidates_stale"] = (
            session_info.get("candidates_stale", False) if session_info else False
        )

    if st.session_state.get("corrections_studio_candidates_stale"):
        st.warning(
            "Candidates were generated with an older detector version. "
            "Click **Regenerate Candidates** to refresh with the current rules and logic."
        )

    if regen_clicked:
        try:
            controller.generate_candidates(session_id, force=True)
            st.session_state["corrections_studio_active_candidate"] = None
            st.session_state["corrections_studio_candidates_stale"] = False
            st.session_state.pop("corrections_studio_preview_cache", None)
            st.rerun()
        except Exception as e:
            st.error(f"Error regenerating candidates: {e}")

    # -- Progress --
    stats = controller.get_session_stats(session_id)
    _render_progress_bar(stats)

    st.divider()

    # -- Filter controls --
    kind_options = ["memory_hit", "acronym", "consistency", "fuzzy", "ner_variant"]
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([1, 1, 1, 1])
    with filter_col1:
        status_options = ["all", "pending", "accepted", "rejected", "skipped"]
        status_filter = st.selectbox(
            "Filter by status",
            status_options,
            key="corrections_studio_status_filter",
        )
    with filter_col2:
        kind_filter = st.multiselect(
            "Kind",
            kind_options,
            default=[],
            key="corrections_studio_kind_filter",
            help="Leave empty for all kinds",
        )
    with filter_col3:
        confidence_min = st.slider(
            "Min confidence",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.05,
            key="corrections_studio_confidence_min",
        )
    with filter_col4:
        page_size = 50
        total_count = controller.count_candidates(
            session_id,
            status_filter=status_filter if status_filter != "all" else None,
            kind_filter=kind_filter if kind_filter else None,
            confidence_min=confidence_min if confidence_min > 0 else None,
        )
        total_pages = max(1, (total_count + page_size - 1) // page_size)
        page_num = st.number_input(
            f"Page (1–{total_pages})",
            min_value=1,
            max_value=total_pages,
            value=min(st.session_state.get("corrections_studio_page", 1), total_pages),
            step=1,
            key="corrections_studio_page",
        )

    offset = (page_num - 1) * page_size
    sf = status_filter if status_filter != "all" else None
    kf = kind_filter if kind_filter else None
    cf = confidence_min if confidence_min > 0 else None
    candidates = controller.list_candidates(
        session_id,
        status_filter=sf,
        kind_filter=kf,
        confidence_min=cf,
        offset=offset,
        limit=page_size,
    )

    if not candidates:
        st.info("No candidates match the current filter.")
        return

    # -- Layout: candidate list + detail panel --
    list_col, detail_col = st.columns([3, 7])

    with list_col:
        st.markdown("#### Candidates")
        active_id = st.session_state.get("corrections_studio_active_candidate")
        for c in candidates:
            status_emoji = {
                "pending": "",
                "accepted": "[ok]",
                "rejected": "[x]",
                "skipped": "[-]",
            }.get(c["status"], "")
            wrong_preview = c["wrong_text"][:30] + (
                "…" if len(c["wrong_text"]) > 30 else ""
            )
            suggested_preview = c["suggested_text"][:30] + (
                "…" if len(c["suggested_text"]) > 30 else ""
            )
            label = (
                f"{c['kind']} {status_emoji} — {wrong_preview} → {suggested_preview}"
            )
            is_active = active_id == c["id"]
            btn_type = "primary" if is_active else "secondary"
            if st.button(
                label,
                key=f"cand_{c['id']}",
                width="stretch",
                type=btn_type,
            ):
                st.session_state["corrections_studio_active_candidate"] = c["id"]
                st.rerun()

    with detail_col:
        active_id = st.session_state.get("corrections_studio_active_candidate")
        active_candidate = next((c for c in candidates if c["id"] == active_id), None)
        if active_candidate is None and candidates:
            active_candidate = candidates[0]
            st.session_state["corrections_studio_active_candidate"] = active_candidate[
                "id"
            ]

        if active_candidate:
            _render_candidate_detail(controller, session_id, active_candidate)

    # -- Preview & Export --
    st.divider()
    preview_col, export_col = st.columns([1, 1])
    with preview_col:
        if st.button("Compute Full Preview"):
            try:
                preview = controller.compute_preview(session_id)
                st.session_state["corrections_studio_preview_cache"] = preview
                st.success(
                    f"Preview computed: {preview['stats']['applied_count']} corrections applied"
                )
            except Exception as e:
                st.error(f"Preview error: {e}")

    with export_col:
        if st.session_state.get("corrections_studio_confirm_export"):
            confirm_col1, confirm_col2 = st.columns(2)
            with confirm_col1:
                if st.button("Yes, Export", type="primary", key="export_confirm_yes"):
                    try:
                        result = controller.apply_and_export(session_id)
                        st.session_state["corrections_studio_export_success"] = result
                        st.session_state.pop("corrections_studio_session_id", None)
                        st.session_state.pop("corrections_studio_confirm_export", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Export error: {e}")
            with confirm_col2:
                if st.button("Cancel", key="export_confirm_cancel"):
                    st.session_state.pop("corrections_studio_confirm_export", None)
                    st.rerun()
        elif st.button("Apply & Export", type="primary"):
            st.session_state["corrections_studio_confirm_export"] = True
            st.rerun()

    preview_data = st.session_state.get("corrections_studio_preview_cache")
    if preview_data:
        with st.expander("Preview Patch Log", expanded=False):
            non_policy = [
                e
                for e in preview_data.get("patch_log", [])
                if "resolution_policy" not in e
            ]
            for entry in non_policy[:20]:
                st.markdown(
                    f"**{entry.get('segment_id', '?')[:8]}** "
                    f"`{entry.get('before', '')[:60]}` → `{entry.get('after', '')[:60]}`"
                )
            if len(non_policy) > 20:
                st.caption(f"... and {len(non_policy) - 20} more")


def is_corrections_studio_enabled() -> bool:
    return os.environ.get("TRANSCRIPTX_ENABLE_CORRECTIONS_STUDIO", "1") == "1"
