"""
Speaker Identification page — interactive speaker-by-speaker naming.

Groups segments by diarized speaker ID, shows sample lines for the active
speaker, supports audio clip playback (if audio is available), and lets the
user assign a name or mark as ignored before moving to the next speaker.

The audio player + segment rows are rendered via render_playback_panel()
(@st.fragment), so play-button clicks rerun only that region — the rest of
the page (header, metrics, name assignment, navigation) does not dim.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import streamlit as st

from transcriptx.app.models.results import RunSummary
from transcriptx.core.utils.file_discovery import discover_managed_transcript_paths
from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.io.speaker_map_resolver import (
    is_effective_speaker_name,
    normalize_diarized_id,
)
from transcriptx.services.speaker_studio.segment_index import SegmentInfo
from transcriptx.web.action_menus.context import ActionContext, build_canonical_identity
from transcriptx.web.action_menus.ids import NavStyle, SectionId
from transcriptx.web.action_menus.render import render_configured_actions
from transcriptx.web.components.playback_panel import (
    clear_playback_session_keys,
    fmt_time as _fmt_time,
    render_playback_panel,
    sanitize_lines_shown,
    sanitize_play_index,
)
from transcriptx.web.components.recent_run_row import render_recent_run_actions
from transcriptx.web.cache_helpers import (
    cached_get_transcript_summaries_for_paths,
    cached_list_all_transcript_summaries,
    cached_list_available_sessions,
    clear_transcript_listing_caches,
)
from transcriptx.web.speaker_profile_signals import consume_cache_invalidation_signal
from transcriptx.web.speaker_studio_runtime import get_shared_speaker_studio_controller
from transcriptx.web.services.file_service import FileService
from transcriptx.web.state import SELECTBOX_PLACEHOLDER_TRANSCRIPT
from transcriptx.web.transcript_option_format import (
    format_transcript_option_with_speaker_status,
)
from transcriptx.web.navigation import (
    make_session_path_resolver,
)
from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.services.transcript_context_resolver import (
    resolve_transcript_context,
)

# How many sample lines to show per speaker by default
_LINES_PER_PAGE = 8

# Non-transcript JSON names under run dirs (skip when scanning outputs)
_RUN_DIR_JSON_SKIP = frozenset(
    {"manifest.json", "run_results.json", "processing_state.json"}
)


@st.cache_data(ttl=120, show_spinner=False)
def _transcript_paths_for_speaker_views() -> list:
    """Cached so transcript dropdown/selection doesn't trigger full discovery on every rerun."""
    return _transcript_paths_for_speaker_views_impl()


def _transcript_paths_for_speaker_views_impl() -> list[Path]:
    """Same discovery as Library and session-based views; also scan run dirs (Docker-friendly)."""
    paths: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        key = str(p.resolve())
        if key not in seen and p.exists():
            seen.add(key)
            paths.append(p)

    for p in discover_managed_transcript_paths(None):
        add(Path(p))

    for session in cached_list_available_sessions():
        name = session.get("name", "")
        if "/" not in name:
            continue
        resolved = FileService.resolve_transcript_path(name)
        if resolved:
            add(Path(resolved))

    # Docker: manifest transcript_path is often host-only; scan run dirs for transcript-like JSON
    from transcriptx.core.utils.paths import OUTPUTS_DIR

    outputs_dir = Path(OUTPUTS_DIR)
    if outputs_dir.is_dir():
        for slug_dir in outputs_dir.iterdir():
            if not slug_dir.is_dir() or slug_dir.name.startswith("."):
                continue
            for run_dir in slug_dir.iterdir():
                if not run_dir.is_dir() or run_dir.name.startswith("."):
                    continue
                for j in run_dir.glob("*.json"):
                    if (
                        j.name in _RUN_DIR_JSON_SKIP
                        or j.parent.name == ".transcriptx"
                        or j.name == "report.json"
                    ):
                        continue
                    add(j)

    return sorted(paths, key=lambda p: str(p.resolve()))


def _cached_transcripts_for_paths(paths_key: tuple[str, ...]) -> list:
    """Return transcript list for given paths so selectbox/UI doesn't recompute on every rerun."""
    # Delegate to cache_helpers (read-only index); never construct a controller.
    return cached_get_transcript_summaries_for_paths(paths_key)


def _cached_fallback_transcripts() -> list:
    """Fallback when no paths from discovery; avoids full list_transcripts on every rerun."""
    return cached_list_all_transcript_summaries()


# ── helpers ──────────────────────────────────────────────────────────────────


def _speaker_id_transcript_label(t) -> str:
    """Dropdown label: for partial maps, add unnamed vs ignored speaker counts."""
    return format_transcript_option_with_speaker_status(t)


def _speaker_map_display_name(speaker_map: Dict[str, str], sid: str) -> str:
    """
    Resolve display name for a diarized speaker id.

    Sidecar keys are normalized (e.g. SPEAKER_01); segment ids may appear in a
    variant form (e.g. SPEAKER_1). Try normalized key first, then raw sid.
    """
    nid = normalize_diarized_id(sid)
    if nid:
        v = speaker_map.get(nid)
        if is_effective_speaker_name(nid, v):
            return str(v).strip()
    v = speaker_map.get(sid)
    if is_effective_speaker_name(sid, v):
        return str(v).strip()
    return ""


def _is_speaker_ignored(ignored: List[str], sid: str) -> bool:
    """True if sid is ignored, accepting raw or normalized diarized-id forms."""
    nid = normalize_diarized_id(sid)
    if not nid and not sid:
        return False
    for ig in ignored or []:
        if ig is None or not str(ig).strip():
            continue
        raw = str(ig).strip()
        if sid == raw or (nid and nid == raw):
            return True
        if nid and normalize_diarized_id(raw) == nid:
            return True
    return False


def _clear_speaker_id_listing_caches() -> None:
    """Drop stale speaker-map status labels after save/ignore/unignore."""
    clear_transcript_listing_caches()


def _group_by_diarized_id(
    segments: List[SegmentInfo],
) -> Dict[str, List[SegmentInfo]]:
    """Return ordered dict: diarized_id → list of SegmentInfo."""
    groups: Dict[str, List[SegmentInfo]] = defaultdict(list)
    seen_order: List[str] = []
    for seg in segments:
        did = seg.speaker_diarized_id or seg.speaker
        if did and did not in groups:
            seen_order.append(did)
        if did:
            groups[did].append(seg)
    return {k: groups[k] for k in seen_order}


def _voice_analyse_segment_dicts(segments: List[SegmentInfo]) -> list[dict]:
    """Build segment dicts for voice analyse using diarized IDs.

    ``SegmentInfo.speaker`` may already be a remapped display name; voice
    excerpt selection keys on the diarized ID, so always prefer
    ``speaker_diarized_id``. Pass the full transcript (all speakers) so overlap
    filtering against other speakers can run.
    """
    out: list[dict] = []
    for s in segments:
        did = s.speaker_diarized_id or s.speaker
        out.append(
            {
                "speaker": did,
                "speaker_diarized_id": did,
                "start": s.start,
                "end": s.end,
                "text": s.text or "",
            }
        )
    return out


def _latest_run_summary_for_transcript(transcript_path: Path) -> RunSummary | None:
    """Build a RunSummary for the newest run linked to this transcript, if any."""
    resolution = resolve_transcript_context(
        transcript_path,
        session_resolver=make_session_path_resolver(),
    )
    subject_id = resolution.subject_id
    run_id = resolution.run_id
    if not subject_id or not run_id:
        return None
    # Raw filesystem paths are not output slugs.
    if "/" in subject_id or "\\" in subject_id or Path(subject_id).suffix:
        return None
    run_dir = Path(OUTPUTS_DIR) / subject_id / run_id
    if not run_dir.is_dir():
        return None
    try:
        created_at = datetime.fromtimestamp(run_dir.stat().st_mtime)
    except OSError:
        created_at = datetime.now()
    return RunSummary(
        run_dir=run_dir,
        transcript_path=Path(transcript_path),
        run_id=run_id,
        created_at=created_at,
        selected_modules=[],
    )


def _render_post_speaker_id_actions(transcript_path: Path) -> None:
    """Configured action strip under Speaker ID completion."""
    run = _latest_run_summary_for_transcript(transcript_path)
    if run is not None:
        render_recent_run_actions(
            run,
            row_index=0,
            key_prefix="speaker_id_run",
            section=SectionId.SPEAKER_ID_COMPLETE,
        )
        return

    identity = build_canonical_identity(
        subject_type="transcript",
        subject_id=transcript_path.stem,
        transcript_path=transcript_path,
    )
    ctx = ActionContext(
        identity=identity,
        widget_identity=f"speaker_id_{transcript_path.stem}",
        nav_style=NavStyle.ON_CLICK,
        instance_prefix="speaker_id",
        rename_supported=True,
        run_completed=False,
    )
    render_configured_actions(SectionId.SPEAKER_ID_COMPLETE, ctx)


# ── main render ──────────────────────────────────────────────────────────────


def render_speaker_id_page() -> None:
    """Render the speaker-by-speaker identification page."""
    st.markdown(
        '<div class="main-header">Speaker Identification</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Work through each speaker one at a time: review their lines, "
        "play a clip, then assign a name or mark as ignored."
    )

    controller = get_shared_speaker_studio_controller()
    paths = _transcript_paths_for_speaker_views()
    if paths:
        paths_key = tuple(str(p) for p in paths)
        transcripts = _cached_transcripts_for_paths(paths_key)
    else:
        transcripts = []
    if not transcripts:
        transcripts = _cached_fallback_transcripts()
    if not transcripts:
        st.info("No transcripts found. Add transcript JSON files first.")
        return

    # ── transcript picker ────────────────────────────────────────────────────
    options = [t.path for t in transcripts]
    labels = [_speaker_id_transcript_label(t) for t in transcripts]
    n = len(options)
    default_idx = SubjectService.index_in_path_options(st.session_state, options)

    idx = st.selectbox(
        "Transcript",
        range(n + 1),
        format_func=lambda i: (
            SELECTBOX_PLACEHOLDER_TRANSCRIPT if i == 0 else labels[i - 1]
        ),
        index=default_idx,
        key="speaker_id_transcript",
    )
    if idx == 0:
        return
    transcript_path = options[idx - 1]
    SubjectService.set_transcript_context_from_path(
        st.session_state,
        transcript_path,
        session_resolver=make_session_path_resolver(),
    )

    # Re-load whenever transcript changes
    prev_key = "speaker_id_prev_transcript"
    if st.session_state.get(prev_key) != transcript_path:
        st.session_state[prev_key] = transcript_path
        st.session_state["speaker_id_speaker_idx"] = 0
        st.session_state["speaker_id_lines_shown"] = _LINES_PER_PAGE
        clear_playback_session_keys("speaker_id_play_seg")
        # Keep jump selectbox (key sid_jump) aligned — its widget state otherwise
        # overrides Prev/Next on the next rerun.
        st.session_state["sid_jump"] = 0

    # ── load segments + map ───────────────────────────────────────────────────
    try:
        segments = controller.list_segments(transcript_path)
        map_state = controller.get_mapping_status(transcript_path)
    except Exception as exc:
        st.error(
            f"Speaker mapping file is corrupt for this transcript: {exc}. "
            "Please re-identify speakers or delete the sidecar."
        )
        return

    if not segments:
        st.info("No segments found in this transcript.")
        return

    speaker_map: Dict[str, str] = map_state.speaker_map or {}
    ignored: List[str] = getattr(map_state, "ignored_speakers", None) or []

    groups = _group_by_diarized_id(segments)
    speaker_ids = list(groups.keys())
    total_speakers = len(speaker_ids)

    if total_speakers == 0:
        st.info("No speaker IDs found in this transcript.")
        return

    audio_path = controller.get_audio_path(transcript_path)

    # ── progress summary ──────────────────────────────────────────────────────
    named = sum(
        1
        for sid in speaker_ids
        if _speaker_map_display_name(speaker_map, sid)
        and not _is_speaker_ignored(ignored, sid)
    )
    n_ignored = sum(1 for sid in speaker_ids if _is_speaker_ignored(ignored, sid))
    remaining = total_speakers - named - n_ignored

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Speakers", total_speakers)
    col_b.metric("Named", named)
    col_c.metric("Ignored", n_ignored)
    col_d.metric("Remaining", remaining)

    if remaining == 0 and total_speakers > 0:
        st.success("All speakers identified!")
        _render_post_speaker_id_actions(Path(transcript_path))

    st.divider()

    # ── speaker navigation state ──────────────────────────────────────────────
    raw_speaker_idx = st.session_state.get("speaker_id_speaker_idx", 0)
    speaker_idx = sanitize_play_index(raw_speaker_idx, total_speakers)
    if speaker_idx is None:
        speaker_idx = 0
        st.session_state["speaker_id_speaker_idx"] = 0
        st.session_state["sid_jump"] = 0
    else:
        st.session_state["speaker_id_speaker_idx"] = speaker_idx

    # Jump selectbox is session-state keyed; initialize once (do not pass index=).
    if "sid_jump" not in st.session_state:
        st.session_state["sid_jump"] = speaker_idx
    else:
        jump = sanitize_play_index(st.session_state["sid_jump"], total_speakers)
        if jump is None:
            st.session_state["sid_jump"] = speaker_idx
        else:
            st.session_state["sid_jump"] = jump

    active_id = speaker_ids[speaker_idx]
    active_segs = groups[active_id]
    current_name = _speaker_map_display_name(speaker_map, active_id)
    is_ignored = _is_speaker_ignored(ignored, active_id)

    # ── speaker header ────────────────────────────────────────────────────────
    status_badge = (
        "🔇 ignored"
        if is_ignored
        else (f"✅ **{current_name}**" if current_name.strip() else "❓ unnamed")
    )
    st.subheader(
        f"Speaker {speaker_idx + 1} / {total_speakers} — `{active_id}` {status_badge}"
    )
    lines_shown = sanitize_lines_shown(
        st.session_state.get("speaker_id_lines_shown", _LINES_PER_PAGE),
        length=len(active_segs),
        default=_LINES_PER_PAGE,
    )
    st.session_state["speaker_id_lines_shown"] = lines_shown
    total_dur = sum(max(0.0, s.end - s.start) for s in active_segs)
    st.caption(
        f"{len(active_segs)} segments · {_fmt_time(total_dur)} total · "
        f"showing {min(lines_shown, len(active_segs))} of {len(active_segs)} lines"
    )

    # ── playback panel (fragment) ─────────────────────────────────────────────
    # Only this region reruns on play-button clicks; the rest of the page is
    # unaffected.  All expensive data work was done above and is passed in.
    render_playback_panel(
        controller=controller,
        transcript_path=transcript_path,
        audio_path=audio_path,
        all_segs=active_segs,
        active_id=active_id,
        play_key="speaker_id_play_seg",
        lines_key="speaker_id_lines_shown",
        max_lines=_LINES_PER_PAGE,
        autoplay=True,
        include_segment_rows=True,
    )

    st.divider()

    # ── name assignment ───────────────────────────────────────────────────────
    from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver

    _profile_resolver = ManagedTranscriptResolver()
    is_managed_for_profiles = _profile_resolver.is_managed_path(transcript_path)

    # Voice matching: gated by ActivationBarrier.
    if is_managed_for_profiles and not is_ignored:
        try:
            from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
            from transcriptx.core.speaker_profiles.voice.activation import (
                ActivationBarrier,
            )
            from transcriptx.io.speaker_map_resolver import normalize_diarized_id
            from transcriptx.services.speaker_profiles.voice_facade import (
                SpeakerIdVoiceFacade,
                ensure_idempotency_key,
                voice_session_key,
            )

            _voice_status = ActivationBarrier(speaker_profiles_dir()).status()
            if not _voice_status.allowed:
                st.caption(
                    "Local voice suggestions are not available yet "
                    f"({_voice_status.block_reason or 'unavailable'})."
                )
            else:
                st.markdown("##### Voice suggestions")
                st.caption(
                    "Probabilistic local match — not identity verification. "
                    "Confirming uses the existing profile-link workflow."
                )
                facade = SpeakerIdVoiceFacade()
                resolved = _profile_resolver.resolve_path(transcript_path)
                lsk = normalize_diarized_id(active_id)
                result_key = voice_session_key(
                    resolved.managed_transcript_id, lsk, "result"
                )
                # Full transcript with diarized IDs — remapped display names in
                # SegmentInfo.speaker must not starve excerpt selection.
                voice_seg_dicts = _voice_analyse_segment_dicts(segments)
                btn_one, btn_all = st.columns(2)
                if btn_one.button(
                    "Analyse voice",
                    key=f"sid_voice_analyse_{active_id}",
                    help="Embed this speaker and rank local profile suggestions.",
                ):
                    with st.spinner("Analysing voice…"):
                        st.session_state[result_key] = facade.analyse(
                            transcript_path=Path(transcript_path),
                            raw_speaker=active_id,
                            segments=voice_seg_dicts,
                        )
                if btn_all.button(
                    "Analyse all speakers",
                    key="sid_voice_analyse_all",
                    help=(
                        "Run voice matching for every non-ignored speaker so "
                        "suggestions are ready as you step through the list."
                    ),
                ):
                    targets = [
                        sid
                        for sid in speaker_ids
                        if not _is_speaker_ignored(ignored, sid)
                    ]
                    suggestions = 0
                    no_match = 0
                    other = 0
                    with st.spinner(
                        f"Analysing voice for {len(targets)} speakers…"
                    ):
                        from transcriptx.core.speaker_profiles.voice.match_service import (
                            AnalyseResult as _AnalyseResult,
                        )

                        for sid in targets:
                            sid_key = normalize_diarized_id(sid)
                            sid_result_key = voice_session_key(
                                resolved.managed_transcript_id, sid_key, "result"
                            )
                            try:
                                ar = facade.analyse(
                                    transcript_path=Path(transcript_path),
                                    raw_speaker=sid,
                                    segments=voice_seg_dicts,
                                )
                            except Exception as exc:
                                ar = _AnalyseResult(
                                    outcome="AnalyseFailed",
                                    match=None,
                                    suggestion_id=None,
                                    suggestion_digest=None,
                                    detail=str(exc),
                                )
                            st.session_state[sid_result_key] = ar
                            if ar.outcome == "SuggestionAvailable":
                                suggestions += 1
                            elif ar.outcome == "NoReliableMatch":
                                no_match += 1
                            else:
                                other += 1
                    st.session_state["sid_voice_analyse_all_summary"] = (
                        f"Analysed {len(targets)} speakers: "
                        f"{suggestions} suggestion(s), "
                        f"{no_match} no match, "
                        f"{other} other."
                    )
                    st.rerun()
                batch_summary = st.session_state.pop(
                    "sid_voice_analyse_all_summary", None
                )
                if batch_summary:
                    st.info(batch_summary)
                result = st.session_state.get(result_key)
                if result is not None:
                    if result.outcome == "SuggestionAvailable" and result.candidates_ui:
                        from transcriptx.core.speaker_profiles.service import (
                            SpeakerProfileService,
                        )

                        _name_svc = SpeakerProfileService()
                        for cand in result.candidates_ui:
                            live_profile = _name_svc.get_profile(cand["profile_id"])
                            display = (
                                live_profile.display_name
                                if live_profile is not None
                                else cand.get("display_name") or cand["profile_id"]
                            )
                            st.write(
                                f"**{display}** — {cand['confidence']} "
                                f"({cand['reference_count']} refs)"
                            )
                            accept_key = voice_session_key(
                                resolved.managed_transcript_id,
                                lsk,
                                f"accept_{cand['profile_id']}",
                            )
                            op_key = ensure_idempotency_key(
                                st.session_state, accept_key
                            )
                            cols = st.columns(3)
                            if cols[0].button(
                                "Confirm this profile",
                                key=f"sid_voice_confirm_{active_id}_{cand['profile_id']}",
                            ):
                                try:
                                    from transcriptx.core.speaker_profiles.identity import (
                                        link_file_key,
                                    )

                                    svc = SpeakerProfileService()
                                    live = svc.get_live_link(
                                        link_file_key(
                                            resolved.managed_transcript_id, lsk
                                        )
                                    )
                                    ar = facade.accept(
                                        operation_idempotency_key=op_key,
                                        managed_transcript_id=resolved.managed_transcript_id,
                                        local_speaker_key=lsk,
                                        candidate_profile_id=cand["profile_id"],
                                        suggestion_id=result.suggestion_id or "",
                                        suggestion_digest=result.suggestion_digest
                                        or "",
                                        confidence_category=cand["confidence"],
                                        model_generation_id=result.model_generation_id
                                        or "",
                                        occurrence_fingerprint=result.occurrence_fingerprint
                                        or "",
                                        expected_link_id=(
                                            result.expected_link_id
                                            if result.expected_link_id is not None
                                            else (live.link_id if live else None)
                                        ),
                                        expected_owner_profile_id=(
                                            result.expected_owner_profile_id
                                            if result.expected_owner_profile_id
                                            is not None
                                            else (live.profile_id if live else None)
                                        ),
                                        expected_fingerprint=(
                                            result.expected_fingerprint
                                            if result.expected_fingerprint is not None
                                            else (
                                                live.occurrence_fingerprint
                                                if live
                                                else None
                                            )
                                        ),
                                        expected_audio_stat_fingerprint=result.audio_stat_fingerprint,
                                        expected_audio_content_sha256=result.audio_content_sha256,
                                        query_cache_key=result.query_cache_key,
                                    )
                                    consume_cache_invalidation_signal(ar.cache_signal)
                                    st.session_state.pop(result_key, None)
                                    st.success("Profile link confirmed from suggestion.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(str(exc))
                            if cols[1].button(
                                "Reject suggestion",
                                key=f"sid_voice_reject_{active_id}_{cand['profile_id']}",
                            ):
                                rej_key = voice_session_key(
                                    resolved.managed_transcript_id,
                                    lsk,
                                    f"reject_{cand['profile_id']}",
                                )
                                try:
                                    facade.reject(
                                        operation_idempotency_key=ensure_idempotency_key(
                                            st.session_state, rej_key
                                        ),
                                        managed_transcript_id=resolved.managed_transcript_id,
                                        local_speaker_key=lsk,
                                        occurrence_fingerprint=result.occurrence_fingerprint
                                        or "",
                                        candidate_profile_id=cand["profile_id"],
                                        suggestion_id=result.suggestion_id or "",
                                        suggestion_digest=result.suggestion_digest
                                        or "",
                                        model_generation_id=result.model_generation_id
                                        or "",
                                        reference_corpus_digest=result.reference_corpus_digest
                                        or "",
                                        reference_count=int(
                                            cand.get("reference_count") or 0
                                        ),
                                    )
                                    st.info("Suggestion rejected for this evidence set.")
                                    st.session_state.pop(result_key, None)
                                    st.rerun()
                                except Exception as exc:
                                    st.error(str(exc))
                            if cols[2].button(
                                "Leave unlinked",
                                key=f"sid_voice_leave_{active_id}_{cand['profile_id']}",
                            ):
                                facade.acceptance.leave_unlinked()
                                st.session_state.pop(result_key, None)
                                st.info("Left unlinked for this session.")
                                st.rerun()
                    elif result.outcome == "NoReliableMatch":
                        st.info("No reliable voice match.")
                    elif result.outcome == "insufficient_speech":
                        st.warning(
                            "Voice analyse: insufficient speech — need at least "
                            "8 seconds of speech attributed to this speaker."
                        )
                        if result.detail:
                            st.caption(result.detail)
                    else:
                        st.warning(f"Voice analyse: {result.outcome}")
                        if result.detail:
                            st.caption(result.detail)
        except Exception:
            pass

    col_name, col_save, col_ignore = st.columns([3, 1, 1])
    with col_name:
        name_input = st.text_input(
            "Assign name",
            value=current_name,
            key=f"sid_name_{active_id}",
            placeholder="Type speaker name…",
            label_visibility="collapsed",
        )
    link_profile = False
    if is_managed_for_profiles:
        link_profile = st.checkbox(
            "Also link to longitudinal speaker profile",
            value=True,
            key=f"sid_link_profile_{active_id}",
            help=(
                "Creates a durable cross-transcript profile link for this managed "
                "library speaker. Ad-hoc / run-output JSON supports local naming only."
            ),
        )
    elif not is_managed_for_profiles:
        st.caption(
            "Longitudinal profile linking is available for managed library "
            "transcripts only. Local naming still works here."
        )
    with col_save:
        if st.button("Save name", key="sid_save", type="primary", width="stretch"):
            name = (name_input or "").strip()
            if name:
                try:
                    if link_profile and is_managed_for_profiles:
                        from transcriptx.services.speaker_profiles.create_and_name import (
                            create_profile_link_and_name,
                        )

                        partial = create_profile_link_and_name(
                            transcript_path=transcript_path,
                            raw_speaker=active_id,
                            display_name=name,
                            controller=controller,
                            create_profile=True,
                            apply_sidecar_name=True,
                            method="web",
                        )
                        consume_cache_invalidation_signal(partial.effective_signal)
                        _clear_speaker_id_listing_caches()
                        if partial.is_partial:
                            st.warning(
                                "Profile link saved, but local naming failed: "
                                f"{partial.naming_error}"
                            )
                        new_state = controller.get_mapping_status(transcript_path)
                    else:
                        new_state = controller.apply_mapping_mutation(
                            transcript_path, active_id, name, method="web"
                        )
                        _clear_speaker_id_listing_caches()
                    st.session_state["speaker_id_lines_shown"] = _LINES_PER_PAGE
                    clear_playback_session_keys("speaker_id_play_seg")
                    # Advance from persisted state (including when this was the last one).
                    next_idx = _next_unnamed_idx(
                        speaker_ids,
                        dict(new_state.speaker_map or {}),
                        list(new_state.ignored_speakers or []),
                        speaker_idx,
                    )
                    st.session_state["speaker_id_speaker_idx"] = next_idx
                    st.session_state["sid_jump"] = next_idx
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            else:
                st.warning("Enter a name before saving.")
    with col_ignore:
        ignore_label = "Unignore" if is_ignored else "Ignore"
        if st.button(ignore_label, key="sid_ignore", width="stretch"):
            try:
                if is_ignored:
                    new_state = controller.unignore_speaker(
                        transcript_path, active_id, method="web"
                    )
                else:
                    new_state = controller.ignore_speaker(
                        transcript_path, active_id, method="web"
                    )
                _clear_speaker_id_listing_caches()
                st.session_state["speaker_id_lines_shown"] = _LINES_PER_PAGE
                clear_playback_session_keys("speaker_id_play_seg")
                # Use persisted ignored list so unignore does not keep treating
                # this id as ignored, and ignore-last still settles on complete.
                next_idx = _next_unnamed_idx(
                    speaker_ids,
                    dict(new_state.speaker_map or {}),
                    list(new_state.ignored_speakers or []),
                    speaker_idx,
                )
                st.session_state["speaker_id_speaker_idx"] = next_idx
                st.session_state["sid_jump"] = next_idx
                st.rerun()
            except Exception as e:
                st.error(str(e))

    # ── prev / next navigation ────────────────────────────────────────────────
    st.divider()
    col_prev, col_jump, col_next = st.columns([1, 3, 1])
    # Run Prev/Next before the jump selectbox: Streamlit disallows assigning to
    # session_state["sid_jump"] after the widget with key sid_jump is created.
    with col_prev:
        if st.button(
            "← Prev",
            key="sid_prev",
            disabled=(speaker_idx == 0),
            width="stretch",
        ):
            st.session_state["speaker_id_speaker_idx"] = speaker_idx - 1
            st.session_state["sid_jump"] = speaker_idx - 1
            st.session_state["speaker_id_lines_shown"] = _LINES_PER_PAGE
            clear_playback_session_keys("speaker_id_play_seg")
            st.rerun()
    with col_next:
        if st.button(
            "Next →",
            key="sid_next",
            disabled=(speaker_idx >= total_speakers - 1),
            width="stretch",
        ):
            st.session_state["speaker_id_speaker_idx"] = speaker_idx + 1
            st.session_state["sid_jump"] = speaker_idx + 1
            st.session_state["speaker_id_lines_shown"] = _LINES_PER_PAGE
            clear_playback_session_keys("speaker_id_play_seg")
            st.rerun()
    with col_jump:
        # Jump-to picker: show all speakers with their current status
        jump_labels = [
            _speaker_label(sid, i, speaker_map, ignored)
            for i, sid in enumerate(speaker_ids)
        ]
        jump_idx = st.selectbox(
            "Jump to speaker",
            range(total_speakers),
            format_func=lambda i: jump_labels[i],
            key="sid_jump",
            label_visibility="collapsed",
        )
        if jump_idx != speaker_idx:
            st.session_state["speaker_id_speaker_idx"] = jump_idx
            # sid_jump is already the user's selection; do not assign it after
            # this widget is instantiated.
            st.session_state["speaker_id_lines_shown"] = _LINES_PER_PAGE
            clear_playback_session_keys("speaker_id_play_seg")
            st.rerun()


# ── utilities ─────────────────────────────────────────────────────────────────


def _speaker_label(
    sid: str,
    idx: int,
    speaker_map: Dict[str, str],
    ignored: List[str],
) -> str:
    name = _speaker_map_display_name(speaker_map, sid)
    if _is_speaker_ignored(ignored, sid):
        return f"{idx + 1}. {sid} 🔇"
    if name:
        return f"{idx + 1}. {sid} → {name}"
    return f"{idx + 1}. {sid} ❓"


def _next_unnamed_idx(
    speaker_ids: List[str],
    speaker_map: Dict[str, str],
    ignored: List[str],
    current: int,
) -> int:
    """Return index of next speaker that has no name and is not ignored, or stay."""
    # Try forward first
    for i in range(current + 1, len(speaker_ids)):
        sid = speaker_ids[i]
        if not _is_speaker_ignored(ignored, sid) and not _speaker_map_display_name(
            speaker_map, sid
        ):
            return i
    # Then try from the beginning
    for i in range(0, current):
        sid = speaker_ids[i]
        if not _is_speaker_ignored(ignored, sid) and not _speaker_map_display_name(
            speaker_map, sid
        ):
            return i
    return current
