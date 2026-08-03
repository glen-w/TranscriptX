"""
Speaker Identification page — interactive speaker-by-speaker naming.

Groups segments by diarized speaker ID, shows sample lines for the active
speaker, supports audio clip playback (if audio is available), and lets the
user assign a name or mark as ignored before moving to the next speaker.

The post-picker workspace runs in ``_speaker_id_workspace_fragment`` so Save /
Ignore / Prev / Next / Jump / Voice only fragment-rerun. Transcript selection
and the transition to completion may full-app rerun. Playback uses
``render_playback_panel_body`` inside that workspace (no nested fragments).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence

import streamlit as st

from transcriptx.app.models.results import RunSummary
from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.io.speaker_map_resolver import (
    is_effective_speaker_name,
    normalize_diarized_id,
)
from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.services.speaker_studio.segment_index import SegmentInfo
from transcriptx.web.action_menus.context import ActionContext, build_canonical_identity
from transcriptx.web.action_menus.ids import NavStyle, SectionId
from transcriptx.web.action_menus.render import render_configured_actions
from transcriptx.web.components.playback_panel import (
    clear_playback_session_keys,
    fmt_time as _fmt_time,
    render_playback_panel_body,
    sanitize_lines_shown,
    sanitize_play_index,
)
from transcriptx.web.components.recent_run_row import render_recent_run_actions
from transcriptx.web.cache_helpers import (
    cached_get_transcript_summaries_for_paths,
    cached_list_all_transcript_summaries,
    cached_speaker_id_segments,
    cached_transcript_paths_for_speaker_views,
    invalidate_transcript_summary_for_path,
    transcript_segments_signature,
    transcript_summary_signature,
)
from transcriptx.web.speaker_profile_signals import consume_cache_invalidation_signal
from transcriptx.web.speaker_studio_runtime import get_shared_speaker_studio_controller
from transcriptx.web.state import (
    IMPORT_LAST_TRANSCRIPT_PATH,
    SELECTBOX_PLACEHOLDER_TRANSCRIPT,
    WORKFLOW_NAV_TRANSCRIPT_PATH,
)
from transcriptx.web.transcript_option_format import (
    format_transcript_option_with_speaker_status,
)
from transcriptx.web.navigation import (
    make_session_path_resolver,
)
from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.services.transcript_context_resolver import (
    paths_match,
    resolve_transcript_context,
)

# How many sample lines to show per speaker by default
_LINES_PER_PAGE = 10
# Non-widget persistence: sidebar can clear canonical subject_id after the page
# selectbox runs; the widget key alone is not enough if Streamlit remounts it.
_SPEAKER_ID_SELECTED_PATH = "speaker_id_selected_path"
_SPEAKER_ID_VOICE_PENDING = "sid_voice_pending"
_SPEAKER_ID_COMPLETION_APP_RERUN = "sid_completion_app_rerun"
_PLAY_KEY = "speaker_id_play_seg"
_LINES_KEY = "speaker_id_lines_shown"


def _transcript_paths_for_speaker_views() -> list:
    """Cached discovery; kept as a page-local alias for tests/signals."""
    return cached_transcript_paths_for_speaker_views()


def _preferred_transcript_path() -> str | None:
    """Path from identity navigation, page selection, last import, or subject."""
    for key in (
        WORKFLOW_NAV_TRANSCRIPT_PATH,
        _SPEAKER_ID_SELECTED_PATH,
        IMPORT_LAST_TRANSCRIPT_PATH,
    ):
        raw = st.session_state.get(key)
        if raw:
            try:
                if Path(raw).is_file():
                    return str(raw)
            except OSError:
                continue
    return SubjectService.current_transcript_path(st.session_state)


def _paths_with_current_subject(paths: list[Path]) -> list[Path]:
    """Ensure navigated subject is listed even if discovery briefly lags import."""
    current = _preferred_transcript_path()
    if not current:
        return list(paths)
    current_path = Path(current)
    try:
        if not current_path.is_file():
            return list(paths)
    except OSError:
        return list(paths)
    if any(paths_match(p, current_path) for p in paths):
        return list(paths)
    return sorted([*paths, current_path], key=lambda p: str(p.resolve()))


def _bind_transcript_picker_index(options: list, default_idx: int) -> None:
    """Force selectbox value when key was cleared or reset to placeholder.

    Streamlit ignores ``index=`` once a keyed widget exists; navigators pop the
    key, then we assign the intended index before instantiating the selectbox.

    Also recover when the widget remounts at placeholder (0) while a preferred
    transcript is still known — Analyse voice can clear canonical subject via
    the sidebar, leaving only this page key; a remount must not strand the user.
    """
    key = "speaker_id_transcript"
    n = len(options)
    if key in st.session_state:
        current = st.session_state.get(key)
        if not isinstance(current, int) or current < 0 or current > n:
            if 0 <= default_idx <= n:
                st.session_state[key] = default_idx
            else:
                st.session_state[key] = 0
            return
        if current == 0 and default_idx > 0:
            st.session_state[key] = default_idx
        return
    if 0 <= default_idx <= n:
        st.session_state[key] = default_idx


def _cached_transcripts_for_paths(paths_key: tuple[str, ...]) -> list:
    """Return transcript list for given paths so selectbox/UI doesn't recompute on every rerun."""
    return cached_get_transcript_summaries_for_paths(paths_key)


def _cached_fallback_transcripts() -> list:
    """Fallback when no paths from discovery; avoids full list_transcripts on every rerun."""
    return cached_list_all_transcript_summaries()


def _rerun_app() -> None:
    """Full-app rerun (completion, or fragment-scope fallback)."""
    st.rerun()


def _rerun_ui() -> None:
    """Rerun the workspace fragment when allowed; otherwise full-app rerun.

    Streamlit rejects ``scope="fragment"`` while the fragment is executing as
    part of a full-app run (even inside a fragment-decorated function). Voice
    deferral, jump sync, and confirm/reject can hit that path — fall back
    instead of surfacing a StreamlitAPIException as "Voice suggestions
    unavailable".
    """
    try:
        st.rerun(scope="fragment")
    except st.errors.StreamlitAPIException:
        _rerun_app()


def _rerun_app_for_completion() -> None:
    """Single intentional full-app rerun: completion paint + picker label refresh."""
    st.session_state[_SPEAKER_ID_COMPLETION_APP_RERUN] = True
    _rerun_app()


def _load_cached_segments(transcript_path: str | Path) -> List[SegmentInfo]:
    """Load segments from the path+mtime_ns+size cache; fail closed on missing files."""
    try:
        path_str = str(Path(transcript_path).resolve())
    except OSError as exc:
        raise FileNotFoundError(f"Transcript unavailable: {transcript_path}") from exc
    signature = transcript_segments_signature(path_str)
    return list(cached_speaker_id_segments(path_str, signature))


def _set_active_speaker(
    target_idx: int,
    *,
    speaker_count: int,
    clear_playback_if_changed: bool = True,
) -> int:
    """Sanitize target index, sync idx/jump, reset lines; clear playback only on change."""
    sanitized = sanitize_play_index(target_idx, speaker_count)
    if sanitized is None:
        sanitized = 0
    prev = sanitize_play_index(
        st.session_state.get("speaker_id_speaker_idx", 0), speaker_count
    )
    changed = prev != sanitized
    st.session_state["speaker_id_speaker_idx"] = sanitized
    st.session_state["sid_jump"] = sanitized
    st.session_state[_LINES_KEY] = _LINES_PER_PAGE
    if clear_playback_if_changed and changed:
        clear_playback_session_keys(_PLAY_KEY)
    return sanitized


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


def _remaining_count(
    speaker_ids: Sequence[str],
    speaker_map: Dict[str, str],
    ignored: List[str],
) -> tuple[int, int, int]:
    named = sum(
        1
        for sid in speaker_ids
        if _speaker_map_display_name(speaker_map, sid)
        and not _is_speaker_ignored(ignored, sid)
    )
    n_ignored = sum(1 for sid in speaker_ids if _is_speaker_ignored(ignored, sid))
    remaining = len(speaker_ids) - named - n_ignored
    return named, n_ignored, remaining


def _after_mapping_mutation(
    *,
    transcript_path: str | Path,
    speaker_ids: Sequence[str],
    new_state,
    speaker_idx: int,
    summary_sig_before: tuple[int, int, int],
) -> None:
    """Invalidate path summary, advance from persisted state, fragment or completion rerun."""
    invalidate_transcript_summary_for_path(
        transcript_path, signature=summary_sig_before
    )
    speaker_map = dict(new_state.speaker_map or {})
    ignored = list(new_state.ignored_speakers or [])
    next_idx = _next_unnamed_idx(list(speaker_ids), speaker_map, ignored, speaker_idx)
    _set_active_speaker(next_idx, speaker_count=len(speaker_ids))
    _, _, remaining = _remaining_count(speaker_ids, speaker_map, ignored)
    if remaining == 0 and len(speaker_ids) > 0:
        _rerun_app_for_completion()
        return
    _rerun_ui()


# ── workspace fragment ────────────────────────────────────────────────────────


@st.fragment
def _speaker_id_workspace_fragment(
    transcript_path: str,
    controller: SpeakerStudioController,
) -> None:
    """Post-picker workspace: stable inputs only; reload map every fragment run."""
    try:
        segments = _load_cached_segments(transcript_path)
        map_state = controller.get_mapping_status(transcript_path)
    except FileNotFoundError as exc:
        st.error(f"Transcript file is missing or unreadable: {exc}")
        return
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

    named, n_ignored, remaining = _remaining_count(speaker_ids, speaker_map, ignored)
    audio_path = controller.get_audio_path(transcript_path)

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Speakers", total_speakers)
    col_b.metric("Named", named)
    col_c.metric("Ignored", n_ignored)
    col_d.metric("Remaining", remaining)

    if remaining == 0 and total_speakers > 0:
        st.success("All speakers identified!")
        _render_post_speaker_id_actions(Path(transcript_path))

    st.divider()

    # Sync jump widget → speaker idx before computing active speaker.
    if "sid_jump" in st.session_state:
        jump = sanitize_play_index(st.session_state["sid_jump"], total_speakers)
        idx_now = sanitize_play_index(
            st.session_state.get("speaker_id_speaker_idx", 0), total_speakers
        )
        if jump is not None and idx_now is not None and jump != idx_now:
            _set_active_speaker(jump, speaker_count=total_speakers)
        elif jump is None:
            st.session_state["sid_jump"] = idx_now if idx_now is not None else 0

    raw_speaker_idx = st.session_state.get("speaker_id_speaker_idx", 0)
    speaker_idx = sanitize_play_index(raw_speaker_idx, total_speakers)
    if speaker_idx is None:
        speaker_idx = _set_active_speaker(0, speaker_count=total_speakers)
    else:
        st.session_state["speaker_id_speaker_idx"] = speaker_idx
        if "sid_jump" not in st.session_state:
            st.session_state["sid_jump"] = speaker_idx

    active_id = speaker_ids[speaker_idx]
    active_segs = groups[active_id]
    current_name = _speaker_map_display_name(speaker_map, active_id)
    is_ignored = _is_speaker_ignored(ignored, active_id)

    status_badge = (
        "🔇 ignored"
        if is_ignored
        else (f"✅ **{current_name}**" if current_name.strip() else "❓ unnamed")
    )
    st.subheader(
        f"Speaker {speaker_idx + 1} / {total_speakers} — `{active_id}` {status_badge}"
    )
    lines_shown = sanitize_lines_shown(
        st.session_state.get(_LINES_KEY, _LINES_PER_PAGE),
        length=len(active_segs),
        default=_LINES_PER_PAGE,
    )
    st.session_state[_LINES_KEY] = lines_shown
    total_dur = sum(max(0.0, s.end - s.start) for s in active_segs)
    st.caption(
        f"{len(active_segs)} segments · {_fmt_time(total_dur)} total · "
        f"showing {min(lines_shown, len(active_segs))} of {len(active_segs)} lines"
    )

    render_playback_panel_body(
        controller=controller,
        transcript_path=str(transcript_path),
        audio_path=audio_path,
        all_segs=active_segs,
        active_id=active_id,
        play_key=_PLAY_KEY,
        lines_key=_LINES_KEY,
        max_lines=_LINES_PER_PAGE,
        autoplay=True,
        include_segment_rows=True,
    )

    st.divider()

    from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver

    _profile_resolver = ManagedTranscriptResolver()
    is_managed_for_profiles = _profile_resolver.is_managed_path(transcript_path)

    if is_managed_for_profiles and not is_ignored:
        _render_voice_suggestions(
            transcript_path=transcript_path,
            segments=segments,
            speaker_ids=speaker_ids,
            ignored=ignored,
            active_id=active_id,
            profile_resolver=_profile_resolver,
        )

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
                    summary_sig = transcript_summary_signature(transcript_path)
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
                    _after_mapping_mutation(
                        transcript_path=transcript_path,
                        speaker_ids=speaker_ids,
                        new_state=new_state,
                        speaker_idx=speaker_idx,
                        summary_sig_before=summary_sig,
                    )
                except Exception as e:
                    st.error(str(e))
            else:
                st.warning("Enter a name before saving.")
    with col_ignore:
        ignore_label = "Unignore" if is_ignored else "Ignore"
        if st.button(ignore_label, key="sid_ignore", width="stretch"):
            try:
                summary_sig = transcript_summary_signature(transcript_path)
                if is_ignored:
                    new_state = controller.unignore_speaker(
                        transcript_path, active_id, method="web"
                    )
                else:
                    new_state = controller.ignore_speaker(
                        transcript_path, active_id, method="web"
                    )
                _after_mapping_mutation(
                    transcript_path=transcript_path,
                    speaker_ids=speaker_ids,
                    new_state=new_state,
                    speaker_idx=speaker_idx,
                    summary_sig_before=summary_sig,
                )
            except Exception as e:
                st.error(str(e))

    st.divider()
    col_prev, col_jump, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button(
            "← Prev",
            key="sid_prev",
            disabled=(speaker_idx == 0),
            width="stretch",
        ):
            _set_active_speaker(speaker_idx - 1, speaker_count=total_speakers)
            _rerun_ui()
    with col_next:
        if st.button(
            "Next →",
            key="sid_next",
            disabled=(speaker_idx >= total_speakers - 1),
            width="stretch",
        ):
            _set_active_speaker(speaker_idx + 1, speaker_count=total_speakers)
            _rerun_ui()
    with col_jump:
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
            _set_active_speaker(jump_idx, speaker_count=total_speakers)
            _rerun_ui()


def _render_voice_suggestions(
    *,
    transcript_path: str | Path,
    segments: List[SegmentInfo],
    speaker_ids: Sequence[str],
    ignored: List[str],
    active_id: str,
    profile_resolver,
) -> None:
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
        facade = SpeakerIdVoiceFacade()
        resolved = profile_resolver.resolve_path(transcript_path)
        lsk = normalize_diarized_id(active_id)
        result_key = voice_session_key(
            resolved.managed_transcript_id, lsk, "result"
        )
        pending_peek = st.session_state.get(_SPEAKER_ID_VOICE_PENDING)
        batch_summary_peek = st.session_state.get("sid_voice_analyse_all_summary")
        expand_voice = bool(
            pending_peek
            or batch_summary_peek
            or st.session_state.get(result_key) is not None
        )
        with st.expander("Voice suggestions", expanded=expand_voice):
            if not _voice_status.allowed:
                st.caption(
                    "Local voice suggestions are not available yet "
                    f"({_voice_status.block_reason or 'unavailable'})."
                )
                return

            st.caption(
                "Probabilistic local match — not identity verification. "
                "Confirming uses the existing profile-link workflow."
            )
            voice_seg_dicts = _voice_analyse_segment_dicts(segments)
            btn_one, btn_all = st.columns(2)
            if btn_one.button(
                "Analyse voice",
                key=f"sid_voice_analyse_{active_id}",
                help="Embed this speaker and rank local profile suggestions.",
            ):
                st.session_state[_SPEAKER_ID_VOICE_PENDING] = {
                    "mode": "one",
                    "speaker": active_id,
                    "transcript": str(transcript_path),
                }
                _rerun_ui()
            if btn_all.button(
                "Analyse all speakers",
                key="sid_voice_analyse_all",
                help=(
                    "Run voice matching for every non-ignored speaker so "
                    "suggestions are ready as you step through the list."
                ),
            ):
                st.session_state[_SPEAKER_ID_VOICE_PENDING] = {
                    "mode": "all",
                    "transcript": str(transcript_path),
                }
                _rerun_ui()

            # Pop before heavy work so exceptions cannot re-queue analyse.
            pending = st.session_state.pop(_SPEAKER_ID_VOICE_PENDING, None)
            pending_path = pending.get("transcript") if pending else None
            if pending and pending_path and paths_match(pending_path, transcript_path):
                if pending.get("mode") == "one":
                    raw_speaker = str(pending.get("speaker") or active_id)
                    with st.spinner("Analysing voice…"):
                        try:
                            one_key = voice_session_key(
                                resolved.managed_transcript_id,
                                normalize_diarized_id(raw_speaker),
                                "result",
                            )
                            st.session_state[one_key] = facade.analyse(
                                transcript_path=Path(transcript_path),
                                raw_speaker=raw_speaker,
                                segments=voice_seg_dicts,
                            )
                        except Exception as exc:
                            st.error(f"Voice analyse failed: {exc}")
                elif pending.get("mode") == "all":
                    targets = [
                        sid
                        for sid in speaker_ids
                        if not _is_speaker_ignored(ignored, sid)
                    ]
                    suggestions = 0
                    no_match = 0
                    other = 0
                    with st.spinner(f"Analysing voice for {len(targets)} speakers…"):
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
                    st.info(
                        f"Analysed {len(targets)} speakers: "
                        f"{suggestions} suggestion(s), "
                        f"{no_match} no match, "
                        f"{other} other."
                    )

            batch_summary = st.session_state.pop(
                "sid_voice_analyse_all_summary", None
            )
            if batch_summary:
                st.info(batch_summary)
            result = st.session_state.get(result_key)
            if result is None:
                return
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
                    op_key = ensure_idempotency_key(st.session_state, accept_key)
                    cols = st.columns(3)
                    if cols[0].button(
                        "Confirm this profile",
                        key=(
                            f"sid_voice_confirm_{active_id}_" f"{cand['profile_id']}"
                        ),
                    ):
                        try:
                            from transcriptx.core.speaker_profiles.identity import (
                                link_file_key,
                            )

                            svc = SpeakerProfileService()
                            live = svc.get_live_link(
                                link_file_key(resolved.managed_transcript_id, lsk)
                            )
                            ar = facade.accept(
                                operation_idempotency_key=op_key,
                                managed_transcript_id=resolved.managed_transcript_id,
                                local_speaker_key=lsk,
                                candidate_profile_id=cand["profile_id"],
                                suggestion_id=result.suggestion_id or "",
                                suggestion_digest=result.suggestion_digest or "",
                                confidence_category=cand["confidence"],
                                model_generation_id=result.model_generation_id or "",
                                occurrence_fingerprint=(
                                    result.occurrence_fingerprint or ""
                                ),
                                expected_link_id=(
                                    result.expected_link_id
                                    if result.expected_link_id is not None
                                    else (live.link_id if live else None)
                                ),
                                expected_owner_profile_id=(
                                    result.expected_owner_profile_id
                                    if result.expected_owner_profile_id is not None
                                    else (live.profile_id if live else None)
                                ),
                                expected_fingerprint=(
                                    result.expected_fingerprint
                                    if result.expected_fingerprint is not None
                                    else (
                                        live.occurrence_fingerprint if live else None
                                    )
                                ),
                                expected_audio_stat_fingerprint=(
                                    result.audio_stat_fingerprint
                                ),
                                expected_audio_content_sha256=(
                                    result.audio_content_sha256
                                ),
                                query_cache_key=result.query_cache_key,
                            )
                            consume_cache_invalidation_signal(ar.cache_signal)
                            st.session_state.pop(result_key, None)
                            st.success("Profile link confirmed from suggestion.")
                            _rerun_ui()
                        except Exception as exc:
                            st.error(str(exc))
                    if cols[1].button(
                        "Reject suggestion",
                        key=(
                            f"sid_voice_reject_{active_id}_" f"{cand['profile_id']}"
                        ),
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
                                occurrence_fingerprint=(
                                    result.occurrence_fingerprint or ""
                                ),
                                candidate_profile_id=cand["profile_id"],
                                suggestion_id=result.suggestion_id or "",
                                suggestion_digest=result.suggestion_digest or "",
                                model_generation_id=result.model_generation_id or "",
                                reference_corpus_digest=(
                                    result.reference_corpus_digest or ""
                                ),
                                reference_count=int(
                                    cand.get("reference_count") or 0
                                ),
                            )
                            st.info("Suggestion rejected for this evidence set.")
                            st.session_state.pop(result_key, None)
                            _rerun_ui()
                        except Exception as exc:
                            st.error(str(exc))
                    if cols[2].button(
                        "Leave unlinked",
                        key=(
                            f"sid_voice_leave_{active_id}_" f"{cand['profile_id']}"
                        ),
                    ):
                        facade.acceptance.leave_unlinked()
                        st.session_state.pop(result_key, None)
                        st.info("Left unlinked for this session.")
                        _rerun_ui()
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
    except st.errors.StreamlitAPIException:
        raise
    except Exception as exc:
        st.warning(f"Voice suggestions unavailable: {exc}")


# ── main render ──────────────────────────────────────────────────────────────


def render_speaker_id_page() -> None:
    """Render the speaker-by-speaker identification page."""
    # Consume one-shot completion flag so Save/Ignore cannot loop app↔fragment.
    st.session_state.pop(_SPEAKER_ID_COMPLETION_APP_RERUN, None)

    st.markdown(
        '<div class="main-header">Speaker Identification</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Work through each speaker one at a time: review their lines, "
        "play a clip, then assign a name or mark as ignored."
    )

    controller = get_shared_speaker_studio_controller()
    paths = _paths_with_current_subject(_transcript_paths_for_speaker_views())
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

    options = [t.path for t in transcripts]
    labels = [_speaker_id_transcript_label(t) for t in transcripts]
    n = len(options)
    preferred = _preferred_transcript_path()
    default_idx = 0
    if preferred:
        for i, opt in enumerate(options):
            if paths_match(opt, preferred):
                default_idx = i + 1
                break
    if default_idx == 0:
        default_idx = SubjectService.index_in_path_options(st.session_state, options)
    _bind_transcript_picker_index(options, default_idx)
    st.session_state.pop(WORKFLOW_NAV_TRANSCRIPT_PATH, None)

    idx = st.selectbox(
        "Transcript",
        range(n + 1),
        format_func=lambda i: (
            SELECTBOX_PLACEHOLDER_TRANSCRIPT if i == 0 else labels[i - 1]
        ),
        key="speaker_id_transcript",
    )
    if idx == 0:
        st.session_state.pop(_SPEAKER_ID_SELECTED_PATH, None)
        return
    transcript_path = options[idx - 1]
    st.session_state[_SPEAKER_ID_SELECTED_PATH] = str(transcript_path)
    SubjectService.set_transcript_context_from_path(
        st.session_state,
        transcript_path,
        session_resolver=make_session_path_resolver(),
    )

    prev_key = "speaker_id_prev_transcript"
    if st.session_state.get(prev_key) != transcript_path:
        st.session_state[prev_key] = transcript_path
        st.session_state["speaker_id_speaker_idx"] = 0
        st.session_state[_LINES_KEY] = _LINES_PER_PAGE
        clear_playback_session_keys(_PLAY_KEY)
        st.session_state["sid_jump"] = 0

    _speaker_id_workspace_fragment(str(transcript_path), controller)


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
    """Advance to the next unnamed, non-ignored speaker after a successful mutation.

    If *current* is still unnamed (e.g. partial profile-link/name failure), stay —
    do not skip a speaker that still needs work.
    """
    if 0 <= current < len(speaker_ids):
        sid = speaker_ids[current]
        if not _is_speaker_ignored(ignored, sid) and not _speaker_map_display_name(
            speaker_map, sid
        ):
            return current
    for i in range(current + 1, len(speaker_ids)):
        sid = speaker_ids[i]
        if not _is_speaker_ignored(ignored, sid) and not _speaker_map_display_name(
            speaker_map, sid
        ):
            return i
    for i in range(0, current):
        sid = speaker_ids[i]
        if not _is_speaker_ignored(ignored, sid) and not _speaker_map_display_name(
            speaker_map, sid
        ):
            return i
    return current
