"""
Speaker Identification page — interactive speaker-by-speaker naming.

Groups segments by diarized speaker ID, shows sample lines for the active
speaker, supports audio clip playback (if audio is available), and lets the
user assign a name or mark as ignored before moving to the next speaker.

The post-picker workspace runs in ``_speaker_id_workspace_fragment``. Ordinary
actions (Save / Ignore / Prev / Next / Jump / Voice / CCv2 commands) use
module-level ``on_click`` / ``on_change`` callbacks so mutations run before
the natural fragment rerun — no mid-render ``_rerun_ui`` on those paths.
Callbacks must not rerun the app (no-op + client warning) or display
elements (fragment-callback warning that paints at the top of the app).
Completion only sets ``_SPEAKER_ID_COMPLETION_APP_RERUN``; the fragment body
performs the full-app rerun so the outer picker label refreshes. Playback lives
in the CCv2 workspace (no nested fragments).
Voice is a lightweight conditional block, not a sibling/nested fragment.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence

import streamlit as st

from transcriptx.web.components.page_shell import render_page_shell

from transcriptx.web import icons as ic
from transcriptx.app.models.results import RunSummary
from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.io.speaker_map_resolver import (
    is_effective_speaker_name,
    normalize_diarized_id,
)
from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.services.speaker_studio.segment_index import SegmentInfo
from transcriptx.web.action_menus.context import ActionContext, build_canonical_identity
from transcriptx.web.components.info_tooltip import widget_help
from transcriptx.web.action_menus.ids import NavStyle, SectionId
from transcriptx.web.action_menus.render import render_configured_actions
from transcriptx.web.components.playback_panel import (
    clear_playback_session_keys,
    resolve_playback_context,
    sanitize_lines_shown,
    sanitize_play_index,
)
from transcriptx.web.components.recent_run_row import render_recent_run_actions
from transcriptx.web.cache_helpers import (
    cached_speaker_id_segments,
    cached_transcript_paths_for_speaker_views,
    cached_transcript_summary_for_path,
    invalidate_transcript_summary_for_path,
    load_speaker_identification_index,
    transcript_segments_signature,
    transcript_summary_signature,
)
from transcriptx.web.speaker_profile_signals import consume_cache_invalidation_signal
from transcriptx.web.speaker_studio_runtime import get_shared_speaker_studio_controller
from transcriptx.web.state import (
    IMPORT_LAST_TRANSCRIPT_PATH,
    SELECTBOX_PLACEHOLDER_TRANSCRIPT,
    SPEAKERS_SELECTED_PROFILE_KEY,
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
from transcriptx.web.workspaces.speaker_id_session_keys import (
    TranscriptProfileContext,
    _consume_flash,
    _set_flash,
    _transcript_ns,
    flash_key,
    jump_key,
    lines_key,
    link_mode_key,
    link_profile_key,
    name_widget_key,
    play_key,
    speaker_idx_key,
    voice_batch_summary_key,
    voice_display_key,
    voice_gate_key,
    voice_loaded_key,
    voice_pending_key,
    widget_key,
)
from transcriptx.web.workspaces.speaker_id_voice import (
    _cb_load_voice,
    _cb_voice_analyse_all,
    _cb_voice_analyse_one,
    _cb_voice_confirm,
    _cb_voice_confirm_action,
    _cb_voice_leave,
    _cb_voice_reject,
    _cb_voice_reject_action,
    _render_voice_suggestions,
    _voice_candidates_for_active,
    _voice_display_from_result,
    _voice_recipe_hint,
)
from transcriptx.web.workspaces.speaker_id_actions import (
    _after_mapping_mutation,
    _apply_ack,
    _apply_ccv2_workspace_command,
    _apply_mapping_advance,
    _cb_apply_auto_identify,
    _cb_ccv2_command,
    _cb_ignore_toggle,
    _cb_jump_change,
    _cb_next,
    _cb_prev,
    _cb_save_name,
    _cb_suggest_speaker_names,
    _ccv2_last_ack_key,
    _ccv2_processed_action_key,
    _current_speaker_idx,
    _drain_pending_ccv2_command,
    _get_action_service,
    _next_unnamed_idx,
    _set_active_speaker,
    _validate_callback_identity,
    navigate_to_speaker,
    sync_jump_widget,
)

__all__ = [
    "TranscriptProfileContext",
    "consume_cache_invalidation_signal",
    "invalidate_transcript_summary_for_path",
    "_cb_load_voice",
    "_cb_voice_analyse_all",
    "_cb_voice_analyse_one",
    "_cb_voice_confirm",
    "_cb_voice_confirm_action",
    "_cb_voice_leave",
    "_cb_voice_reject",
    "_cb_voice_reject_action",
    "_consume_flash",
    "_render_voice_suggestions",
    "_set_flash",
    "_transcript_ns",
    "_voice_candidates_for_active",
    "_voice_display_from_result",
    "_voice_recipe_hint",
    "flash_key",
    "jump_key",
    "lines_key",
    "link_mode_key",
    "link_profile_key",
    "name_widget_key",
    "play_key",
    "speaker_idx_key",
    "voice_batch_summary_key",
    "voice_display_key",
    "voice_gate_key",
    "voice_loaded_key",
    "voice_pending_key",
    "widget_key",
]

# How many sample lines to show per speaker by default
_LINES_PER_PAGE = 10
# Non-widget persistence: sidebar can clear canonical subject_id after the page
# selectbox runs; the widget key alone is not enough if Streamlit remounts it.
_SPEAKER_ID_SELECTED_PATH = "speaker_id_selected_path"
_SPEAKER_ID_COMPLETION_APP_RERUN = "sid_completion_app_rerun"

# Legacy aliases used by older tests / call sites that expect module constants.
# Prefer the transcript-scoped helpers below for new code.
_PLAY_KEY = "speaker_id_play_seg"
_LINES_KEY = "speaker_id_lines_shown"
_SPEAKER_ID_VOICE_PENDING = "sid_voice_pending"


@st.cache_data(ttl=300, show_spinner=False)
def _cached_transcript_profile_context(path_str: str) -> TranscriptProfileContext:
    """Process-scoped profile context keyed by resolved transcript path."""
    from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver

    resolver = ManagedTranscriptResolver()
    if not resolver.is_managed_path(path_str):
        return TranscriptProfileContext(is_managed=False)
    try:
        resolved = resolver.resolve_path(path_str)
        return TranscriptProfileContext(
            is_managed=True,
            managed_transcript_id=resolved.managed_transcript_id,
        )
    except Exception:
        return TranscriptProfileContext(is_managed=True, managed_transcript_id=None)


def _resolve_profile_context(transcript_path: str | Path) -> TranscriptProfileContext:
    try:
        path_str = str(Path(transcript_path).resolve())
    except OSError:
        path_str = str(transcript_path)
    return _cached_transcript_profile_context(path_str)


def _profile_listing_items():
    from transcriptx.core.speaker_profiles.aggregates import list_profiles
    from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir

    try:
        return list_profiles(root=speaker_profiles_dir())
    except Exception:
        return []


def _live_link_for_active(
    *,
    profile_ctx: TranscriptProfileContext,
    active_id: str,
):
    from transcriptx.core.speaker_profiles.service import SpeakerProfileService
    from transcriptx.services.speaker_profiles.link_targets import (
        live_link_for_occurrence,
    )

    if not profile_ctx.is_managed:
        return None
    try:
        svc = SpeakerProfileService()
        return live_link_for_occurrence(
            managed_transcript_id=profile_ctx.managed_transcript_id,
            raw_speaker=active_id,
            get_live_link=svc.get_live_link,
        )
    except Exception:
        return None


def _link_targets_for_active(
    *,
    transcript_path: str | Path,
    active_id: str,
    draft_name: str,
    profile_ctx: TranscriptProfileContext,
):
    from transcriptx.services.speaker_profiles.link_targets import suggest_link_targets

    return suggest_link_targets(
        display_name=draft_name,
        managed=profile_ctx.is_managed,
        listing=_profile_listing_items(),
        live_link=_live_link_for_active(profile_ctx=profile_ctx, active_id=active_id),
        voice_candidates=_voice_candidates_for_active(transcript_path, active_id),
        recipe_hint=_voice_recipe_hint(profile_ctx=profile_ctx),
    )


def _target_token(target) -> str:
    if target.mode == "existing" and target.profile_id:
        return f"existing:{target.profile_id}"
    return str(target.mode)


def _render_link_target_panel(
    *,
    transcript_path: str | Path,
    active_id: str,
    draft_name: str,
    profile_ctx: TranscriptProfileContext,
) -> None:
    """Explicit profile destination (create / attach / name only)."""
    from transcriptx.web.navigation import navigate_to_speaker_profile

    targets = _link_targets_for_active(
        transcript_path=transcript_path,
        active_id=active_id,
        draft_name=draft_name,
        profile_ctx=profile_ctx,
    )
    tokens = [_target_token(t) for t in targets.targets]
    labels = {_target_token(t): t.label for t in targets.targets}
    default = targets.default_target()
    default_token = _target_token(default) if default is not None else "none"
    mode_key = link_mode_key(transcript_path, active_id)
    if st.session_state.get(mode_key) not in tokens:
        st.session_state[mode_key] = (
            default_token
            if default_token in tokens
            else (tokens[0] if tokens else "none")
        )
    if targets.recipe_hint:
        st.caption(targets.recipe_hint)
    chosen = st.selectbox(
        "Link to speaker profile",
        options=tokens,
        format_func=lambda tok: labels.get(tok, tok),
        key=mode_key,
        help=widget_help(
            "Choose the longitudinal person this diarized speaker should attach to. "
            "The menu lists existing profiles; name, alias, and voice matches come first. "
            "Create new starts a profile; Name only updates this transcript. "
            "Voice suggestions are assistive — confirm to apply."
        ),
    )
    selected = next(
        (t for t in targets.targets if _target_token(t) == chosen),
        default,
    )
    if selected is not None:
        if selected.duplicate_name_warning:
            st.warning(
                "A profile with this display name already exists. "
                "Attach to it unless you intend to create a duplicate."
            )
        elif selected.detail:
            st.caption(selected.detail)
        if selected.mode == "existing" and selected.profile_id:
            if st.button(
                "Open this profile",
                key=widget_key(transcript_path, f"open_profile_{active_id}"),
                icon=ic.OPEN_IN_NEW,
            ):
                st.session_state[SPEAKERS_SELECTED_PROFILE_KEY] = selected.profile_id
                navigate_to_speaker_profile(selected.profile_id)


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
    """Force selectbox value when key was cleared or reset to placeholder."""
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
    """Deprecated heavy path — retained for tests; prefer path+label listing."""
    from transcriptx.web.cache_helpers import cached_get_transcript_summaries_for_paths

    return cached_get_transcript_summaries_for_paths(paths_key)


def _cached_fallback_transcripts() -> list:
    """Deprecated heavy fallback — retained for tests."""
    from transcriptx.web.cache_helpers import cached_list_all_transcript_summaries

    return cached_list_all_transcript_summaries()


def _light_transcript_picker_rows(paths: list[Path]) -> tuple[list[Path], list[str]]:
    """Build picker options/labels without parsing segments for every path."""
    from transcriptx.web.transcript_option_format import (
        decorate_transcript_picker_label_with_speaker_id,
        speaker_id_status_labels_for_paths,
    )

    options = list(paths)
    status_by_path = speaker_id_status_labels_for_paths(options)
    labels = [
        decorate_transcript_picker_label_with_speaker_id(
            p.stem or str(p),
            status_label=status_by_path.get(str(p), "Unknown"),
        )
        for p in options
    ]
    return options, labels


def _rerun_app() -> None:
    """Full-app rerun from page/fragment body (never from a widget callback)."""
    st.rerun()


def _rerun_ui() -> None:
    """Legacy fragment-scope rerun helper retained for illegal-scope fallback tests.

    Ordinary Save/Ignore/Nav/Voice paths must not call this — callbacks + the
    natural fragment rerun are the single paint. Completion sets a flag via
    ``_rerun_app_for_completion``; the fragment body calls
    ``_commit_completion_app_rerun``.
    """
    try:
        st.rerun(scope="fragment")
    except st.errors.StreamlitAPIException:
        _rerun_app()


_CLIP_POLL_MAX = 16

_CLIP_POLL_SLEEP_S = 0.2


def _samples_awaiting_clip(data: dict) -> bool:
    for row in data.get("samples") or []:
        if row.get("clip_b64"):
            continue
        if str(row.get("clip_status") or "") in {"pending", "inflight", "miss"}:
            return True
    return False


def _maybe_poll_pending_clips(transcript_path: str | Path, data: dict) -> None:
    """Fragment-rerun while visible clips are still encoding so CCv2 receives clip_b64.

    Streamlit only pushes new ``data=`` on a rerun. CCv2 timer ``setTriggerValue``
    calls are not a reliable heartbeat, so we poll here until hit/unavailable or
    the cap is reached. Skipped under pytest unless ``TX_SID_CLIP_POLL=1``.
    """
    if (
        os.environ.get("PYTEST_CURRENT_TEST")
        and os.environ.get("TX_SID_CLIP_POLL") != "1"
    ):
        return
    poll_key = widget_key(transcript_path, "ccv2_clip_poll")
    if not _samples_awaiting_clip(data):
        st.session_state.pop(poll_key, None)
        return
    n = int(st.session_state.get(poll_key, 0) or 0)
    if n >= _CLIP_POLL_MAX:
        return
    st.session_state[poll_key] = n + 1
    time.sleep(_CLIP_POLL_SLEEP_S)
    _rerun_ui()


def _rerun_app_for_completion() -> None:
    """Request a full-app completion refresh; do not rerun from this helper.

    Widget ``on_click`` / ``on_change`` callbacks (including CCv2
    ``on_command_change``) run inside the workspace fragment. A rerun from a
    callback is a no-op and Streamlit warns; displaying elements from that
    callback paints over the top of the app. The fragment body commits via
    ``_commit_completion_app_rerun``.
    """
    st.session_state[_SPEAKER_ID_COMPLETION_APP_RERUN] = True


def _commit_completion_app_rerun() -> None:
    """Full-app rerun from fragment body when completion was requested."""
    if st.session_state.get(_SPEAKER_ID_COMPLETION_APP_RERUN):
        _rerun_app()


def _load_cached_segments(transcript_path: str | Path) -> List[SegmentInfo]:
    """Load segments from the path+mtime_ns+size cache; fail closed on missing files."""
    try:
        path_str = str(Path(transcript_path).resolve())
    except OSError as exc:
        raise FileNotFoundError(f"Transcript unavailable: {transcript_path}") from exc
    signature = transcript_segments_signature(path_str)
    return list(cached_speaker_id_segments(path_str, signature))


def _speaker_id_transcript_label(t) -> str:
    """Label helper for summary objects; light pickers use path stems instead."""
    return format_transcript_option_with_speaker_status(t)


def _speaker_map_display_name(speaker_map: Dict[str, str], sid: str) -> str:
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
    """Return ordered dict: diarized_id → list of SegmentInfo (legacy helper)."""
    from collections import defaultdict

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
    """Build segment dicts for voice analyse using diarized IDs."""
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
    resolution = resolve_transcript_context(
        transcript_path,
        session_resolver=make_session_path_resolver(),
    )
    subject_id = resolution.subject_id
    run_id = resolution.run_id
    if not subject_id or not run_id:
        return None
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
            nav_style=NavStyle.CLICK_RERUN,
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
        nav_style=NavStyle.CLICK_RERUN,
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


def _identify_artefact_row(transcript_path: Path | str, speaker_id: str):
    """Return the identify artefact row for this speaker, if any."""
    try:
        from transcriptx.core.speaker_profiles.identify.artefact import (
            artefact_row_for_speaker,
            load_identify_artefact,
        )

        ctx = _resolve_profile_context(transcript_path)
        if not ctx.is_managed or not ctx.managed_transcript_id:
            return None
        artefact = load_identify_artefact(ctx.managed_transcript_id)
        return artefact_row_for_speaker(artefact, speaker_id)
    except Exception:
        return None


def _identify_badge_suffix(transcript_path: Path | str, speaker_id: str) -> str:
    row = _identify_artefact_row(transcript_path, speaker_id)
    if not row:
        return ""
    bits: list[str] = []
    if row.get("named"):
        bits.append("auto-named")
    if row.get("linked"):
        bits.append("auto-linked")
    if not bits and row.get("action") == "skip" and row.get("skip_reason"):
        return ""
    if not bits:
        return ""
    return " · " + " / ".join(bits)


def _name_suggestion_model_pick_key(transcript_path: str) -> str:
    return widget_key(transcript_path, "name_suggestion_model_tag")


def _load_name_suggestions_for_workspace(
    transcript_path: str,
    profile_ctx: TranscriptProfileContext,
    *,
    force_refresh: bool = False,
    selected_model_tag: str | None = None,
) -> dict[str, Any] | None:
    if not profile_ctx.is_managed or not profile_ctx.managed_transcript_id:
        return None
    from transcriptx.core.speaker_profiles.identify.suggestions import (
        suggest_speaker_names,
    )
    from transcriptx.core.speaker_profiles.identify.suggestions.cache import (
        build_name_suggestions_workspace_payload,
    )
    from transcriptx.core.speaker_profiles.identify.suggestions.service import (
        fingerprint_segments,
    )
    from transcriptx.core.speaker_profiles.resolver import load_transcript_segments

    if force_refresh:
        result = suggest_speaker_names(
            transcript_path,
            managed_transcript_id=profile_ctx.managed_transcript_id,
            force_refresh=True,
        )
        if result.error:
            return {
                "status_message": f"Could not suggest names: {result.error}",
                "llm_used": False,
                "roster": [],
                "by_speaker": {},
            }
        try:
            segments = load_transcript_segments(transcript_path)
            fp = fingerprint_segments(segments)
        except Exception:
            fp = result.transcript_fingerprint
        pick = result.cache_model_tag or selected_model_tag
        if pick:
            st.session_state[_name_suggestion_model_pick_key(transcript_path)] = pick
        return (
            build_name_suggestions_workspace_payload(
                profile_ctx.managed_transcript_id,
                transcript_fingerprint=fp,
                selected_model_tag=pick,
            )
            or result.workspace_payload()
        )

    try:
        segments = load_transcript_segments(transcript_path)
        fp = fingerprint_segments(segments)
    except Exception:
        return None
    pick = selected_model_tag or st.session_state.get(
        _name_suggestion_model_pick_key(transcript_path)
    )
    return build_name_suggestions_workspace_payload(
        profile_ctx.managed_transcript_id,
        transcript_fingerprint=fp,
        selected_model_tag=str(pick) if pick else None,
    )



def _render_managed_identify_actions(
    *,
    transcript_path: str,
    speaker_ids: list[str],
    ignored: List[str],
    active_id: str,
    profile_ctx,
    name_suggestions: dict | None,
) -> None:
    """Suggest names / voice / auto-identify controls (managed library only)."""
    if not profile_ctx.is_managed:
        return
    llm_on = False
    try:
        from transcriptx.core.utils.config import get_config

        cfg = get_config().llm
        llm_on = bool(cfg.enabled and (cfg.provider or "").strip().lower() == "ollama")
    except Exception:
        llm_on = False
    suggest_label = (
        "Suggest names (transcript + LLM)"
        if llm_on
        else "Suggest names (transcript only)"
    )
    st.button(
        suggest_label,
        key=widget_key(transcript_path, "suggest_names"),
        icon=ic.SEARCH,
        help=widget_help(
            "Build a people roster from the transcript and propose names "
            "per speaker. Pick a suggestion in the Name field — nothing is "
            "saved until you choose save (✓). The LLM pass uses the "
            "`speaker_name_suggestions` model from Settings → Models."
        ),
        on_click=_cb_suggest_speaker_names,
        args=(str(transcript_path), profile_ctx),
    )
    available = (name_suggestions or {}).get("available_models") or []
    if len(available) > 1:
        labels = {
            str(row.get("model_tag") or ""): (
                f"{row.get('llm_model') or 'transcript only'}"
                f" — {row.get('status_message') or 'cached'}"
            )
            for row in available
            if row.get("model_tag")
        }
        if labels:
            pick_key = _name_suggestion_model_pick_key(transcript_path)
            tags = list(labels.keys())
            if pick_key not in st.session_state:
                st.session_state[pick_key] = (name_suggestions or {}).get(
                    "selected_model_tag"
                ) or tags[0]
            current = str(st.session_state.get(pick_key) or tags[0])
            if current not in labels:
                st.session_state[pick_key] = tags[0]
                current = tags[0]

            def _on_model_pick_change() -> None:
                st.session_state[pick_key] = st.session_state.get(f"{pick_key}__widget")

            st.selectbox(
                "Suggestion source (model)",
                tags,
                index=tags.index(current),
                format_func=lambda tag: labels.get(tag, tag),
                key=f"{pick_key}__widget",
                on_change=_on_model_pick_change,
            )
    if name_suggestions and name_suggestions.get("status_message"):
        st.caption(str(name_suggestions.get("status_message")))
    with st.expander("Voice suggestions", expanded=False):
        _render_voice_suggestions(
            transcript_path=transcript_path,
            speaker_ids=speaker_ids,
            ignored=ignored,
            active_id=active_id,
            profile_ctx=profile_ctx,
        )
    st.button(
        "Apply auto-identify",
        key=widget_key(transcript_path, "apply_auto_identify"),
        icon=ic.CHECK_ALL,
        help=widget_help(
            "Run voice + text identification on unnamed speakers and write "
            "display names and profile links when confident. Does not enrol "
            "voice samples. Probabilistic — review names after."
        ),
        on_click=_cb_apply_auto_identify,
        args=(str(transcript_path),),
    )
    st.caption(
        "Auto-identify uses enrolled voices and names in the dialogue. "
        "It is not identity verification."
    )


def _render_ccv2_speaker_workspace(
    *,
    transcript_path: str,
    controller: SpeakerStudioController,
    speaker_ids: list[str],
    speaker_idx: int,
    active_id: str,
    speaker_map: Dict[str, str],
    ignored: List[str],
    active_segs: list,
    current_name: str,
    playback_ctx,
    status_badge: str,
    total_speakers: int,
) -> bool:
    """Mount the packaged CCv2 Speaker ID workspace against the action service.

    Returns True when the CCv2 surface mounted. Returns False when the package
    is unavailable so the caller can fall through to the legacy fragment UI.
    """
    from transcriptx.web.workspaces.speaker_id_bridge import (
        build_workspace_data,
        command_from_workspace_result,
        stable_workspace_key,
    )

    try:
        from transcriptx_workspaces import speaker_id_workspace
    except Exception as exc:
        st.error(
            "Speaker Identification requires the ``transcriptx-workspaces`` package. "
            "Install it with ``pip install -e packages/transcriptx_workspaces`` "
            f"(or ``pip install -e '.[web]'`` from a git checkout). ({exc})"
        )
        return False

    profile_ctx = _resolve_profile_context(transcript_path)
    labels = {
        sid: _speaker_label(sid, i, speaker_map, ignored)
        for i, sid in enumerate(speaker_ids)
    }
    l_key = lines_key(transcript_path)
    lines_shown = sanitize_lines_shown(
        st.session_state.get(l_key, _LINES_PER_PAGE),
        length=len(active_segs),
        default=_LINES_PER_PAGE,
    )
    st.session_state[l_key] = lines_shown
    visible_segs = active_segs[:lines_shown]
    samples = [
        {
            "start": float(s.start),
            "end": float(s.end),
            "text": s.text or "",
        }
        for s in visible_segs
    ]
    last_ack = st.session_state.get(_ccv2_last_ack_key(transcript_path))
    link_set = _link_targets_for_active(
        transcript_path=transcript_path,
        active_id=active_id,
        draft_name=current_name,
        profile_ctx=profile_ctx,
    )
    model_pick_key = _name_suggestion_model_pick_key(str(transcript_path))
    name_suggestions = _load_name_suggestions_for_workspace(
        str(transcript_path),
        profile_ctx,
        selected_model_tag=st.session_state.get(model_pick_key),
    )
    data = build_workspace_data(
        transcript_path=str(transcript_path),
        speaker_ids=speaker_ids,
        active_speaker_id=active_id,
        speaker_labels=labels,
        speaker_map=speaker_map,
        ignored_speakers=ignored,
        samples=samples,
        controller=controller,
        audio_path=getattr(playback_ctx, "audio_path", None),
        link_profile_allowed=profile_ctx.is_managed,
        draft_name=current_name,
        ui_status=f"{speaker_idx + 1}/{total_speakers} · {status_badge}",
        last_ack=last_ack if isinstance(last_ack, dict) else None,
        samples_total=len(active_segs),
        samples_page_size=_LINES_PER_PAGE,
        link_targets=link_set.to_workspace_payload(),
        recipe_hint=link_set.recipe_hint,
        name_suggestions=name_suggestions,
    )

    _render_managed_identify_actions(
        transcript_path=transcript_path,
        speaker_ids=speaker_ids,
        ignored=ignored,
        active_id=active_id,
        profile_ctx=profile_ctx,
        name_suggestions=name_suggestions,
    )

    result_key = stable_workspace_key(str(Path(transcript_path).resolve()))

    def _on_command() -> None:
        _cb_ccv2_command(str(transcript_path))

    result = speaker_id_workspace(
        data=data,
        key=result_key,
        on_command_change=_on_command,
    )
    command = command_from_workspace_result(result)
    if command is None:
        command = command_from_workspace_result(st.session_state.get(result_key))

    if command:
        applied, ack_dict = _apply_ccv2_workspace_command(
            str(transcript_path),
            speaker_ids,
            speaker_idx,
            command,
            controller=controller,
            audio_path=getattr(playback_ctx, "audio_path", None),
            samples_total=len(active_segs),
        )
        new_id = (ack_dict or {}).get("active_speaker_id")
        action = str(command.get("action") or "")
        # Completion must full-app rerun from the fragment body (not a callback).
        if st.session_state.get(_SPEAKER_ID_COMPLETION_APP_RERUN):
            _commit_completion_app_rerun()
        # Return-value-only commands land after this paint already used the
        # previous speaker / line count. Fragment-rerun so UI matches.
        elif applied and new_id and new_id != active_id:
            _rerun_ui()
        elif applied and action in {
            "load_more_samples",
            "enqueue_clip",
            "refresh_clips",
        }:
            _rerun_ui()
        elif (
            action == "load_more_samples"
            and not applied
            and len(data.get("samples") or [])
            < int(st.session_state.get(l_key, 0) or 0)
        ):
            # Callback already bumped lines_shown after this paint's data=
            # was built; rerun once so Show-more is not stuck at the old page.
            _rerun_ui()

    _maybe_poll_pending_clips(transcript_path, data)

    return True


@st.fragment
def _speaker_id_workspace_fragment(
    transcript_path: str,
    controller: SpeakerStudioController,
) -> None:
    """Post-picker workspace: reload map every run; index from cache."""
    # Callbacks only set this flag; a rerun from a callback is a no-op.
    _commit_completion_app_rerun()
    _consume_flash(transcript_path)

    try:
        index = load_speaker_identification_index(transcript_path)
        map_state = controller.get_mapping_status(transcript_path)
    except FileNotFoundError as exc:
        st.error(f"Transcript file is missing or unreadable: {exc}")
        return
    except ValueError as exc:
        message = str(exc)
        if "schema" in message.lower() or "schema_version" in message:
            st.error(
                f"This transcript is not a managed library artifact yet: {exc}. "
                "Import it via Import Transcript (or Settings → Watcher auto-import) "
                "so canonical schema markers and an import sidecar are written."
            )
        else:
            st.error(f"Could not load this transcript: {exc}")
        return
    except Exception as exc:
        st.error(
            f"Speaker mapping file is corrupt for this transcript: {exc}. "
            "Please re-identify speakers or delete the sidecar."
        )
        return

    speaker_ids = list(index.ordered_speaker_ids)
    total_speakers = len(speaker_ids)
    if total_speakers == 0:
        st.info("No speaker IDs found in this transcript.")
        return

    speaker_map: Dict[str, str] = map_state.speaker_map or {}
    ignored: List[str] = getattr(map_state, "ignored_speakers", None) or []
    named, n_ignored, remaining = _remaining_count(speaker_ids, speaker_map, ignored)
    playback_ctx = resolve_playback_context(controller, transcript_path)

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Speakers", total_speakers)
    col_b.metric("Named", named)
    col_c.metric("Ignored", n_ignored)
    col_d.metric("Remaining", remaining)

    if remaining == 0 and total_speakers > 0:
        st.success("All speakers identified!")
        _render_post_speaker_id_actions(Path(transcript_path))

    st.divider()

    idx_key = speaker_idx_key(transcript_path)
    j_key = jump_key(transcript_path)
    raw_speaker_idx = st.session_state.get(idx_key, 0)
    speaker_idx = sanitize_play_index(raw_speaker_idx, total_speakers)
    if speaker_idx is None:
        speaker_idx = navigate_to_speaker(
            0, transcript_path=transcript_path, speaker_count=total_speakers
        )
        sync_jump_widget(speaker_idx, transcript_path=transcript_path)
    else:
        st.session_state[idx_key] = speaker_idx
        if j_key not in st.session_state:
            st.session_state[j_key] = speaker_idx
    st.session_state["speaker_id_speaker_idx"] = speaker_idx

    # Phase 9: CCv2 is the only naming/playback surface.
    speaker_idx = _drain_pending_ccv2_command(
        str(transcript_path), speaker_ids, speaker_idx
    )
    st.session_state[idx_key] = speaker_idx
    st.session_state["speaker_id_speaker_idx"] = speaker_idx

    active_id = speaker_ids[speaker_idx]
    active_segs = list(index.segments_by_speaker[active_id])
    current_name = _speaker_map_display_name(speaker_map, active_id)
    is_ignored = _is_speaker_ignored(ignored, active_id)

    status_badge = (
        "🔇 ignored"
        if is_ignored
        else (f"✅ **{current_name}**" if current_name.strip() else "❓ unnamed")
    )
    if not is_ignored:
        status_badge = status_badge + _identify_badge_suffix(transcript_path, active_id)

    mounted = _render_ccv2_speaker_workspace(
        transcript_path=transcript_path,
        controller=controller,
        speaker_ids=speaker_ids,
        speaker_idx=speaker_idx,
        active_id=active_id,
        speaker_map=speaker_map,
        ignored=ignored,
        active_segs=active_segs,
        current_name=current_name,
        playback_ctx=playback_ctx,
        status_badge=status_badge,
        total_speakers=total_speakers,
    )
    _commit_completion_app_rerun()
    if not mounted:
        return


def render_speaker_id_page() -> None:
    """Render the speaker-by-speaker identification page."""
    st.session_state.pop(_SPEAKER_ID_COMPLETION_APP_RERUN, None)

    render_page_shell(
        "Speaker Identification",
        "Work through each speaker one at a time: review their lines, "
        "play a clip, then assign a name or mark as ignored.",
    )

    controller = get_shared_speaker_studio_controller()
    paths = _paths_with_current_subject(_transcript_paths_for_speaker_views())
    if not paths:
        st.info("No transcripts found. Add transcript JSON files first.")
        return

    options, labels = _light_transcript_picker_rows(paths)
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
    try:
        summary = cached_transcript_summary_for_path(
            str(transcript_path),
            transcript_summary_signature(transcript_path),
        )
    except Exception:
        summary = None
    if summary is not None:
        st.caption(format_transcript_option_with_speaker_status(summary))

    prev_key = "speaker_id_prev_transcript"
    path_str = str(transcript_path)
    if st.session_state.get(prev_key) != path_str:
        st.session_state[prev_key] = path_str
        st.session_state[speaker_idx_key(path_str)] = 0
        st.session_state[lines_key(path_str)] = _LINES_PER_PAGE
        clear_playback_session_keys(play_key(path_str))
        st.session_state[jump_key(path_str)] = 0
        st.session_state["speaker_id_speaker_idx"] = 0

    _speaker_id_workspace_fragment(path_str, controller)
