"""
Corrections Studio: DB-backed, resumable correction review in the browser.

Candidate filters and browsing run in ``@st.fragment`` so filter changes do not
trigger a full-app rerun.

Calls only CorrectionsStudioController (no direct service/repo imports).
"""

from __future__ import annotations

import os

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.services.corrections_studio.controller import (
    CorrectionsStudioController,
)
from transcriptx.services.corrections_studio.schema import (
    CandidateLocalDiffResult,
    StudioCandidate,
    StudioReviewStats,
    StudioSessionDocument,
)
from transcriptx.app.corrections import (
    CorrectionsActionService,
    CorrectionsCommand,
    new_corrections_action_id,
)
from transcriptx.web.navigation import make_session_path_resolver
from transcriptx.web.components.info_tooltip import widget_help
from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.state import SELECTBOX_PLACEHOLDER_TRANSCRIPT


def _session_revision(session: StudioSessionDocument | None, session_id: str) -> str:
    """Derive a revision token for optimistic corrections commands."""
    if session is None:
        return f"sess:{session_id}"
    updated = getattr(session, "updated_at", None) or getattr(
        session, "created_at", None
    )
    return f"sess:{session_id}:{updated}"


def _candidate_revision(candidate: StudioCandidate | None, candidate_id: str) -> str:
    if candidate is None:
        return f"cand:{candidate_id}"
    review_status = getattr(candidate, "review_status", None)
    status = (
        review_status.value
        if hasattr(review_status, "value")
        else (str(review_status) if review_status is not None else "")
    )
    digest = (
        getattr(candidate, "suggestion_digest", None)
        or getattr(candidate, "digest", None)
        or ""
    )
    return f"cand:{candidate_id}:{status}:{digest}"


def _next_corrections_action_seq() -> int:
    return int(st.session_state.get("corrections_action_seq", 0)) + 1


def _record_decision_via_action_service(
    controller: CorrectionsStudioController,
    *,
    session_id: str,
    candidate_id: str,
    action: str,
    session: StudioSessionDocument | None = None,
    candidate: StudioCandidate | None = None,
    **payload,
) -> bool:
    """Theme C Phase 6: route review decisions through revisioned command/ack."""
    # Controller has no built-in revision probes; bind tokens so stale checks work.
    sess_rev = _session_revision(session, session_id)
    cand_rev = _candidate_revision(candidate, candidate_id)
    controller.session_revision = lambda _sid: sess_rev  # type: ignore[attr-defined]
    controller.candidate_revision = (  # type: ignore[attr-defined]
        lambda _sid, _cid: cand_rev
    )
    svc = CorrectionsActionService(controller)
    ack = svc.execute(
        CorrectionsCommand(
            action=action,  # type: ignore[arg-type]
            session_id=session_id,
            action_id=new_corrections_action_id(),
            action_seq=_next_corrections_action_seq(),
            expected_session_revision=sess_rev,
            expected_candidate_revision=cand_rev,
            candidate_id=candidate_id,
            payload=payload,
        )
    )
    st.session_state["corrections_action_seq"] = ack.action_seq
    if ack.status != "ok":
        st.warning(ack.message or f"Decision not applied ({ack.status})")
        return False
    return True


def _apply_and_export_via_action_service(
    controller: CorrectionsStudioController,
    *,
    session_id: str,
    session: StudioSessionDocument | None = None,
    **payload,
):
    """Theme C Phase 6: server-authoritative, duplicate-safe apply/export."""
    sess_rev = _session_revision(session, session_id)
    controller.session_revision = lambda _sid: sess_rev  # type: ignore[attr-defined]
    svc = CorrectionsActionService(controller)
    ack = svc.execute(
        CorrectionsCommand(
            action="apply_export",
            session_id=session_id,
            action_id=new_corrections_action_id(),
            action_seq=_next_corrections_action_seq(),
            expected_session_revision=sess_rev,
            payload=payload,
        )
    )
    st.session_state["corrections_action_seq"] = ack.action_seq
    if ack.status != "ok" or not ack.apply_export_committed:
        raise RuntimeError(ack.message or f"Export not applied ({ack.status})")
    return ack.result


@st.cache_data(ttl=120, show_spinner=False)
def _cached_corrections_studio_transcripts() -> list:
    return CorrectionsStudioController().list_transcript_summaries_for_studio()


def _render_progress_bar(stats: StudioReviewStats) -> None:
    pending = stats.pending
    accepted = stats.accepted
    rejected = stats.rejected
    skipped = stats.skipped
    total = pending + accepted + rejected + skipped
    if total == 0:
        st.caption(
            "No candidates yet — propose from the Transcript viewer, or click "
            "**Generate Candidates**."
        )
        return
    done = accepted + rejected + skipped
    st.progress(done / total if total else 0)
    st.caption(
        f"**{pending}** pending | **{accepted}** accepted | "
        f"**{rejected}** rejected | **{skipped}** skipped | "
        f"**{total}** total"
    )


def _get_session_id(session_data: StudioSessionDocument) -> str | None:
    return session_data.session_id or None


def _get_candidate_id(candidate: StudioCandidate) -> str | None:
    return candidate.candidate_id or None


def _candidate_status(candidate: StudioCandidate) -> str:
    return candidate.review_status.value


def _candidate_right_text(candidate: StudioCandidate) -> str:
    return candidate.right_text


def _render_candidate_detail(
    controller: CorrectionsStudioController,
    session_id: str,
    candidate: StudioCandidate,
) -> None:
    candidate_id = _get_candidate_id(candidate)
    if not candidate_id:
        st.error("Candidate is missing an identifier.")
        return
    st.markdown(f"### {candidate.kind} — ranking {candidate.confidence:.2f}")
    sources = [
        s.value if hasattr(s, "value") else str(s) for s in (candidate.sources or [])
    ]
    if sources:
        st.caption("Sources: " + ", ".join(sources))
    st.markdown(f"**{candidate.wrong_text}** → **{_candidate_right_text(candidate)}**")
    st.caption(f"Status: {_candidate_status(candidate)} | ID: {candidate_id[:8]}")

    edit_key = f"corrections_studio_edit_target_{candidate_id}"
    edited = st.text_input(
        "Replacement (editable)",
        value=st.session_state.get(edit_key, candidate.right_text),
        key=edit_key,
    )
    transient = edited if edited != candidate.right_text else None

    diff: CandidateLocalDiffResult = controller.get_candidate_local_diff(
        session_id, candidate_id, transient_target_raw=transient
    )

    if candidate.evidence and (
        candidate.evidence.rationale or candidate.evidence.signals
    ):
        with st.expander("Evidence"):
            st.text((candidate.evidence.rationale or "")[:500])
            sigs = [
                s.value if hasattr(s, "value") else str(s)
                for s in (candidate.evidence.signals or [])
            ]
            if sigs:
                st.caption("Signals: " + ", ".join(sigs))
            st.caption(
                f"Strength: {candidate.evidence.strength.value} · "
                f"Priority: {candidate.evidence.review_priority}"
            )

    # Process pending "Accept selected" from previous run
    pending = st.session_state.get("corrections_studio_pending_accept_selected")
    if pending and pending[0] == candidate_id and pending[1] == session_id:
        st.session_state.pop("corrections_studio_pending_accept_selected", None)
        keys = []
        for i, d in enumerate(diff.diffs):
            if st.session_state.get(f"occ_sel_{candidate_id}_{i}", True):
                sk = d.stable_occurrence_key
                if sk:
                    keys.append(sk)
        review_target = pending[2] if len(pending) > 2 else None
        if _record_decision_via_action_service(
            controller,
            session_id=session_id,
            candidate_id=candidate_id,
            action="accept",
            candidate=candidate,
            selected_occurrence_keys=keys if keys else None,
            review_target_raw=review_target,
        ):
            st.rerun()

    if diff.diffs:
        with st.expander("Occurrences & Diffs", expanded=True):
            for i, d in enumerate(diff.diffs):
                speaker = d.speaker or "?"
                time_info = ""
                if d.time_start is not None:
                    time_end = d.time_end if d.time_end is not None else 0
                    time_info = f" ({d.time_start:.1f}s–{time_end:.1f}s)"
                row1, row2 = st.columns([1, 4])
                with row1:
                    st.checkbox(
                        "Apply",
                        value=True,
                        key=f"occ_sel_{candidate_id}_{i}",
                        help=widget_help("Apply this correction at this occurrence"),
                    )
                with row2:
                    segment_label = d.segment_index if d.segment_index >= 0 else "?"
                    st.markdown(f"**Segment {segment_label}** — {speaker}{time_info}")
                col_before, col_after = st.columns(2)
                with col_before:
                    st.text_area(
                        "Before",
                        value=d.before,
                        height=80,
                        key=f"diff_before_{candidate_id}_{i}",
                        disabled=True,
                    )
                with col_after:
                    st.text_area(
                        "After",
                        value=d.after,
                        height=80,
                        key=f"diff_after_{candidate_id}_{i}",
                        disabled=True,
                    )

    st.divider()
    col_accept, col_accept_sel, col_reject, col_skip, col_learn = st.columns(5)
    with col_accept:
        if st.button(
            "Accept all",
            key=f"accept_{candidate_id}",
            type="primary",
            icon=ic.CHECK_ALL,
        ):
            if _record_decision_via_action_service(
                controller,
                session_id=session_id,
                candidate_id=candidate_id,
                action="accept",
                candidate=candidate,
                review_target_raw=transient,
            ):
                st.rerun()
    with col_accept_sel:
        if st.button(
            "Accept selected",
            key=f"accept_sel_{candidate_id}",
            icon=ic.CHECK,
        ):
            st.session_state["corrections_studio_pending_accept_selected"] = (
                candidate_id,
                session_id,
                transient,
            )
            st.rerun()
    with col_reject:
        if st.button("Reject", key=f"reject_{candidate_id}", icon=ic.REJECT):
            if _record_decision_via_action_service(
                controller,
                session_id=session_id,
                candidate_id=candidate_id,
                action="reject",
                candidate=candidate,
            ):
                st.rerun()
    with col_skip:
        if st.button("Skip", key=f"skip_{candidate_id}", icon=ic.SKIP):
            if _record_decision_via_action_service(
                controller,
                session_id=session_id,
                candidate_id=candidate_id,
                action="skip",
                candidate=candidate,
            ):
                st.rerun()
    with col_learn:
        if st.button(
            "Accept & Learn Rule",
            key=f"learn_{candidate_id}",
            icon=ic.SPELLCHECK,
        ):
            from transcriptx.core.corrections.models import CorrectionRule

            right = _candidate_right_text(candidate)
            rule_hash = CorrectionRule.compute_id(
                candidate.kind,
                [candidate.wrong_text],
                right,
            )
            learn_params = {
                "rule_hash": rule_hash,
                "scope": "global",
                "rule_type": (
                    candidate.kind
                    if candidate.kind in ("token", "phrase", "acronym", "regex")
                    else "phrase"
                ),
                "wrong_variants_json": [candidate.wrong_text],
                "replacement_text": right,
                "confidence": candidate.confidence,
            }
            if _record_decision_via_action_service(
                controller,
                session_id=session_id,
                candidate_id=candidate_id,
                action="accept",
                candidate=candidate,
                learn_rule_params=learn_params,
            ):
                st.rerun()


@st.fragment
def _corrections_studio_workspace_fragment(
    controller: CorrectionsStudioController, session_id: str
) -> None:
    """Filters, candidate list, detail, and export without full-app rerun."""
    stats = controller.get_session_stats(session_id)
    _render_progress_bar(stats)

    diag = controller.get_generation_diagnostics(session_id)
    if diag and isinstance(diag.get("llm"), dict):
        llm = diag["llm"]
        outcome = llm.get("outcome")
        if outcome and outcome not in ("skipped",):
            if outcome == "unavailable":
                st.info("Ollama unavailable; showing deterministic candidates only.")
            elif outcome == "partial":
                st.info(
                    f"Ollama partial: {llm.get('chunks_succeeded', 0)}/"
                    f"{llm.get('chunks_total', 0)} chunks; "
                    f"{llm.get('candidates_grounded', 0)} LLM candidates grounded."
                )
            elif outcome == "failed":
                st.info("Ollama enrichment failed; deterministic candidates retained.")
            elif llm.get("budget_reason"):
                st.info(f"Ollama stopped early ({llm.get('budget_reason')}).")

    st.divider()

    # -- Filter controls --
    kind_options = [
        "memory_hit",
        "acronym",
        "consistency",
        "fuzzy",
        "ner_variant",
        "manual",
    ]
    filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns(
        [1, 1, 1, 1, 1]
    )
    with filter_col1:
        status_options = ["all", "pending", "accepted", "rejected", "skipped"]
        status_filter = st.selectbox(
            "Filter by status",
            status_options,
            key="corrections_studio_status_filter",
            help=widget_help(
                "Review workflow state for each candidate (pending until you accept/reject/skip)."
            ),
        )
    with filter_col2:
        kind_filter = st.multiselect(
            "Kind",
            kind_options,
            default=[],
            key="corrections_studio_kind_filter",
            help=widget_help("Leave empty for all kinds"),
        )
    with filter_col3:
        source_filter = st.multiselect(
            "Source",
            ["memory", "deterministic", "llm", "viewer"],
            default=[],
            key="corrections_studio_source_filter",
            help=widget_help("Leave empty for all sources (viewer = manual propose)"),
        )
    with filter_col4:
        confidence_min = st.slider(
            "Min ranking",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.05,
            key="corrections_studio_confidence_min",
            help=widget_help(
                "Hide candidates below this ranking score (0 = show all)."
            ),
        )
    with filter_col5:
        page_size = 50
        total_count = controller.count_candidates(
            session_id,
            status_filter=status_filter if status_filter != "all" else None,
            kind_filter=kind_filter if kind_filter else None,
            confidence_min=confidence_min if confidence_min > 0 else None,
            source_filter=source_filter if source_filter else None,
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
    sof = source_filter if source_filter else None
    candidates = controller.list_candidates(
        session_id,
        status_filter=sf,
        kind_filter=kf,
        confidence_min=cf,
        source_filter=sof,
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
            candidate_id = _get_candidate_id(c)
            if not candidate_id:
                continue
            st_val = _candidate_status(c)
            status_emoji = {
                "pending": "",
                "accepted": "[ok]",
                "rejected": "[x]",
                "skipped": "[-]",
            }.get(st_val, "")
            wrong_preview = c.wrong_text[:30] + ("…" if len(c.wrong_text) > 30 else "")
            rt = _candidate_right_text(c)
            suggested_preview = rt[:30] + ("…" if len(rt) > 30 else "")
            label = f"{c.kind} {status_emoji} — {wrong_preview} → {suggested_preview}"
            if c.kind == "manual" or any(
                (s.value if hasattr(s, "value") else str(s)) == "viewer_manual"
                for s in (c.sources or [])
            ):
                label = f"[viewer] {label}"
            is_active = active_id == candidate_id
            btn_type = "primary" if is_active else "secondary"
            if st.button(
                label,
                key=f"cand_{candidate_id}",
                width="stretch",
                type=btn_type,
            ):
                st.session_state["corrections_studio_active_candidate"] = candidate_id
                st.rerun()

    with detail_col:
        active_id = st.session_state.get("corrections_studio_active_candidate")
        active_candidate = next(
            (c for c in candidates if _get_candidate_id(c) == active_id),
            None,
        )
        if active_candidate is None and candidates:
            active_candidate = candidates[0]
            st.session_state["corrections_studio_active_candidate"] = _get_candidate_id(
                active_candidate
            )

        if active_candidate:
            _render_candidate_detail(controller, session_id, active_candidate)

    # -- Preview & Export --
    st.divider()
    preview_col, export_col = st.columns([1, 1])
    with preview_col:
        if st.button("Compute Full Preview", icon=ic.PREVIEW):
            try:
                preview = controller.compute_preview(session_id)
                st.session_state["corrections_studio_preview_cache"] = preview
                st.success(
                    f"Preview computed: {preview.stats.applied_count} corrections applied"
                )
            except Exception as e:
                st.error(f"Preview error: {e}")

    with export_col:
        if st.session_state.get("corrections_studio_confirm_export"):
            confirm_col1, confirm_col2 = st.columns(2)
            with confirm_col1:
                if st.button(
                    "Yes, Export",
                    type="primary",
                    key="export_confirm_yes",
                    icon=ic.CONFIRM,
                ):
                    try:
                        result = _apply_and_export_via_action_service(
                            controller,
                            session_id=session_id,
                        )
                        st.session_state["corrections_studio_export_success"] = result
                        st.session_state.pop("corrections_studio_session_id", None)
                        st.session_state.pop("corrections_studio_confirm_export", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Export error: {e}")
            with confirm_col2:
                if st.button("Cancel", key="export_confirm_cancel", icon=ic.CANCEL):
                    st.session_state.pop("corrections_studio_confirm_export", None)
                    st.rerun()
        elif st.button("Apply & Export", type="primary", icon=ic.APPLY):
            st.session_state["corrections_studio_confirm_export"] = True
            st.rerun()

    preview_data = st.session_state.get("corrections_studio_preview_cache")
    if preview_data:
        with st.expander("Preview Patch Log", expanded=False):
            patch_log = (
                preview_data.patch_log
                if hasattr(preview_data, "patch_log")
                else preview_data.get("patch_log", [])
            )
            non_policy = [e for e in patch_log if "resolution_policy" not in e]
            for entry in non_policy[:20]:
                st.markdown(
                    f"**{entry.get('segment_id', '?')[:8]}** "
                    f"`{entry.get('before', '')[:60]}` → `{entry.get('after', '')[:60]}`"
                )
            if len(non_policy) > 20:
                st.caption(f"... and {len(non_policy) - 20} more")


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
        export_path = (
            export_success.export_path
            if hasattr(export_success, "export_path")
            else export_success["export_path"]
        )
        applied_count = (
            export_success.applied_count
            if hasattr(export_success, "applied_count")
            else export_success["applied_count"]
        )
        st.success(
            f"Exported to: {export_path} " f"({applied_count} corrections applied)"
        )

    # -- Transcript selection --
    transcripts = _cached_corrections_studio_transcripts()
    if not transcripts:
        st.info("No transcripts found. Add transcript JSON files to get started.")
        return

    from transcriptx.web.transcript_option_format import decorate_transcript_picker_label

    paths = [t.path for t in transcripts]
    options = [
        decorate_transcript_picker_label(t.base_name, path=t.path) for t in transcripts
    ]
    default_idx = SubjectService.index_in_path_options(st.session_state, paths)
    idx = st.selectbox(
        "Transcript",
        range(len(options) + 1),
        format_func=lambda i: (
            SELECTBOX_PLACEHOLDER_TRANSCRIPT if i == 0 else options[i - 1]
        ),
        index=default_idx,
        key="corrections_studio_transcript",
    )
    if idx == 0:
        return
    transcript_path = paths[idx - 1]
    SubjectService.set_transcript_context_from_path(
        st.session_state,
        transcript_path,
        session_resolver=make_session_path_resolver(),
    )

    # -- Start / Resume / Generate --
    col_start, col_gen, col_regen = st.columns([1, 1, 1])
    with col_start:
        start_clicked = st.button(
            "Start / Resume Session", type="primary", icon=ic.PLAY
        )
    with col_gen:
        generate_clicked = st.button("Generate Candidates", icon=ic.CORRECTIONS)
    with col_regen:
        regen_clicked = st.button("Regenerate Candidates", icon=ic.REPLAY)

    if start_clicked:
        try:
            session_data = controller.start_or_resume(transcript_path)
            session_id = _get_session_id(session_data)
            if not session_id:
                raise KeyError("session_id")
            st.session_state["corrections_studio_session_id"] = session_id
            st.session_state["corrections_studio_candidates_stale"] = (
                session_data.candidates_stale
            )
            st.session_state["corrections_studio_active_candidate"] = None
            # H3: Start/Resume opens the session only — no automatic generation.
            st.rerun()
        except Exception as e:
            st.error(f"Error starting session: {e}")
            return

    session_id = st.session_state.get("corrections_studio_session_id")
    if not session_id:
        return

    # Defer generation to a follow-up run so st.spinner is painted before long work
    # (button handlers alone only show Streamlit's global fade / running icon).
    if generate_clicked:
        st.session_state["corrections_studio_active_candidate"] = None
        st.session_state["corrections_studio_pending_generate"] = True
        st.session_state["corrections_studio_generate_force"] = False
        st.rerun()

    if regen_clicked:
        st.session_state["corrections_studio_active_candidate"] = None
        st.session_state["corrections_studio_pending_generate"] = True
        st.session_state["corrections_studio_generate_force"] = True
        st.rerun()

    if st.session_state.pop("corrections_studio_pending_generate", False):
        force = bool(st.session_state.pop("corrections_studio_generate_force", False))
        try:
            with st.spinner("Generating candidates…"):
                gen_result = controller.generate_candidates(session_id, force=force)
            if getattr(gen_result, "commit_aborted", False):
                st.session_state["corrections_studio_generation_aborted"] = (
                    getattr(gen_result, "abort_reason", "") or "session_changed"
                )
            else:
                st.session_state.pop("corrections_studio_generation_aborted", None)
            st.session_state["corrections_studio_candidates_stale"] = False
            st.session_state.pop("corrections_studio_preview_cache", None)
            st.rerun()
        except Exception as e:
            st.error(f"Error generating candidates: {e}")
            return

    # Ensure stale flag is set when resuming (e.g. returning to page with existing session)
    if "corrections_studio_candidates_stale" not in st.session_state:
        session_info = controller.load_session(session_id)
        st.session_state["corrections_studio_candidates_stale"] = (
            session_info.candidates_stale if session_info else False
        )

    abort_reason = st.session_state.pop("corrections_studio_generation_aborted", None)
    if abort_reason:
        st.warning(
            "Session changed during generation; commit aborted and prior candidates "
            f"kept. Click **Regenerate Candidates** to retry. ({abort_reason})"
        )

    if st.session_state.get("corrections_studio_candidates_stale"):
        st.warning(
            "Candidates were generated with an older detector version. "
            "Click **Regenerate Candidates** to refresh with the current rules and logic."
        )

    _corrections_studio_workspace_fragment(controller, session_id)


def is_corrections_studio_enabled() -> bool:
    return os.environ.get("TRANSCRIPTX_ENABLE_CORRECTIONS_STUDIO", "1") == "1"
