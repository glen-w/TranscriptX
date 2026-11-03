"""Speaker ID mapping / CCv2 command callbacks (shared with the page host).

The page module remains the CCv2 host. Look up page-module names at call time
so tests that monkeypatch ``page_modules.speaker_id`` still apply.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence

import streamlit as st

from transcriptx.app.speaker_id import (
    SpeakerIdActionService,
    SpeakerIdCommand,
    mapping_revision_from_state,
    new_action_id,
    transcript_revision_from_path,
)
from transcriptx.app.speaker_id.effects import apply_speaker_id_ack_effects
from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.web.components.playback_panel import (
    resolve_playback_context,
    sanitize_lines_shown,
    sanitize_play_index,
)
from transcriptx.web.speaker_studio_runtime import get_shared_speaker_studio_controller
from transcriptx.web.workspaces.speaker_id_session_keys import (
    TranscriptProfileContext,
    _set_flash,
    jump_key,
    lines_key,
    link_mode_key,
    name_widget_key,
    play_key,
    speaker_idx_key,
    widget_key,
)


def _page():
    import transcriptx.web.page_modules.speaker_id as page

    return page


def navigate_to_speaker(
    target_idx: int,
    *,
    transcript_path: str | Path,
    speaker_count: int,
    clear_playback_if_changed: bool = True,
) -> int:
    """Canonical speaker navigation: index, lines reset, optional playback clear.

    Does **not** write the jump widget key (use ``sync_jump_widget`` from Prev/Next).
    """
    page = _page()
    sanitized = sanitize_play_index(target_idx, speaker_count)
    if sanitized is None:
        sanitized = 0
    idx_key = speaker_idx_key(transcript_path)
    prev = sanitize_play_index(st.session_state.get(idx_key, 0), speaker_count)
    changed = prev != sanitized
    st.session_state[idx_key] = sanitized
    st.session_state[lines_key(transcript_path)] = page._LINES_PER_PAGE
    if clear_playback_if_changed and changed:
        page.clear_playback_session_keys(play_key(transcript_path))
    return sanitized


def sync_jump_widget(
    speaker_idx: int,
    *,
    transcript_path: str | Path,
) -> None:
    """Update the jump selectbox session value to match canonical index (Prev/Next)."""
    st.session_state[jump_key(transcript_path)] = speaker_idx


def _set_active_speaker(
    target_idx: int,
    *,
    speaker_count: int,
    clear_playback_if_changed: bool = True,
    transcript_path: str | Path | None = None,
) -> int:
    """Backward-compatible wrapper: navigate + sync jump when path is known."""
    page = _page()
    path = transcript_path or st.session_state.get(page._SPEAKER_ID_SELECTED_PATH)
    if not path:
        # Legacy tests without transcript path use global keys.
        sanitized = sanitize_play_index(target_idx, speaker_count)
        if sanitized is None:
            sanitized = 0
        prev = sanitize_play_index(
            st.session_state.get("speaker_id_speaker_idx", 0), speaker_count
        )
        changed = prev != sanitized
        st.session_state["speaker_id_speaker_idx"] = sanitized
        st.session_state["sid_jump"] = sanitized
        st.session_state[page._LINES_KEY] = page._LINES_PER_PAGE
        if clear_playback_if_changed and changed:
            page.clear_playback_session_keys(page._PLAY_KEY)
        return sanitized
    idx = page.navigate_to_speaker(
        target_idx,
        transcript_path=path,
        speaker_count=speaker_count,
        clear_playback_if_changed=clear_playback_if_changed,
    )
    page.sync_jump_widget(idx, transcript_path=path)
    # Mirror legacy keys for tests that still read them when path is set via selected.
    st.session_state["speaker_id_speaker_idx"] = idx
    return idx


def _cb_suggest_speaker_names(
    transcript_path: str, profile_ctx: TranscriptProfileContext
) -> None:
    _page()._load_name_suggestions_for_workspace(
        transcript_path, profile_ctx, force_refresh=True
    )


def _cb_apply_auto_identify(transcript_path: str) -> None:
    from transcriptx.core.speaker_profiles.identify.service import (
        SpeakerIdentifyService,
    )
    from transcriptx.core.utils.logger import get_logger

    try:
        SpeakerIdentifyService().identify_transcript(
            transcript_path,
            auto_name=True,
            auto_link=True,
        )
    except Exception as exc:
        get_logger().warning("Auto-identify failed: %s", exc)


def _next_unnamed_idx(
    speaker_ids: List[str],
    speaker_map: Dict[str, str],
    ignored: List[str],
    current: int,
) -> int:
    """Advance to the next unnamed, non-ignored speaker after a successful mutation."""
    page = _page()
    if 0 <= current < len(speaker_ids):
        sid = speaker_ids[current]
        if not page._is_speaker_ignored(
            ignored, sid
        ) and not page._speaker_map_display_name(speaker_map, sid):
            return current
    for i in range(current + 1, len(speaker_ids)):
        sid = speaker_ids[i]
        if not page._is_speaker_ignored(
            ignored, sid
        ) and not page._speaker_map_display_name(speaker_map, sid):
            return i
    for i in range(0, current):
        sid = speaker_ids[i]
        if not page._is_speaker_ignored(
            ignored, sid
        ) and not page._speaker_map_display_name(speaker_map, sid):
            return i
    return current


def _get_action_service() -> SpeakerIdActionService:
    """Process-scoped action service bound to the shared controller."""
    page = _page()
    controller = get_shared_speaker_studio_controller()
    return SpeakerIdActionService(
        controller,
        # Use the page-module symbols so tests can monkeypatch them.
        index_loader=page.load_speaker_identification_index,
        profile_context_resolver=page._resolve_profile_context,
        voice_confirm=lambda cmd, path, sid: page._cb_voice_confirm(
            path, sid, str((cmd.payload or {}).get("profile_id") or "")
        ),
        voice_reject=lambda cmd, path, sid: page._cb_voice_reject(
            path, sid, str((cmd.payload or {}).get("profile_id") or "")
        ),
    )


def _current_speaker_idx(transcript_path: str | Path, speaker_count: int) -> int:
    idx = sanitize_play_index(
        st.session_state.get(speaker_idx_key(transcript_path), 0),
        speaker_count,
    )
    return 0 if idx is None else idx


def _apply_ack(ack, *, transcript_path: str | Path, speaker_count: int) -> None:
    """Apply action-service acknowledgement effects to the legacy session."""
    page = _page()
    apply_speaker_id_ack_effects(
        ack,
        transcript_path=transcript_path,
        speaker_count=speaker_count,
        set_flash=_set_flash,
        navigate_to_speaker=page.navigate_to_speaker,
        sync_jump_widget=page.sync_jump_widget,
        invalidate_transcript_summary_for_path=page.invalidate_transcript_summary_for_path,
        consume_cache_invalidation_signal=page.consume_cache_invalidation_signal,
        rerun_app_for_completion=page._rerun_app_for_completion,
        session_state=st.session_state,
    )


def _apply_mapping_advance(
    *,
    transcript_path: str | Path,
    speaker_ids: Sequence[str],
    new_state,
    speaker_idx: int,
    summary_sig_before: tuple[int, int, int],
) -> None:
    """Legacy helper: invalidate summary, advance speaker; completion may full-app rerun.

    Kept for characterisation tests and direct callers. Ordinary Save/Ignore
    callbacks go through ``SpeakerIdActionService`` instead.
    Does **not** call ``_rerun_ui`` — the natural fragment rerun paints.
    Completion only sets the flag; the fragment body commits the app rerun.
    """
    page = _page()
    page.invalidate_transcript_summary_for_path(
        transcript_path, signature=summary_sig_before
    )
    speaker_map = dict(new_state.speaker_map or {})
    ignored = list(new_state.ignored_speakers or [])
    next_idx = page._next_unnamed_idx(
        list(speaker_ids), speaker_map, ignored, speaker_idx
    )
    idx = page.navigate_to_speaker(
        next_idx,
        transcript_path=transcript_path,
        speaker_count=len(speaker_ids),
    )
    page.sync_jump_widget(idx, transcript_path=transcript_path)
    st.session_state["speaker_id_speaker_idx"] = idx
    _, _, remaining = page._remaining_count(speaker_ids, speaker_map, ignored)
    if remaining == 0 and len(speaker_ids) > 0:
        page._rerun_app_for_completion()


def _after_mapping_mutation(
    *,
    transcript_path: str | Path,
    speaker_ids: Sequence[str],
    new_state,
    speaker_idx: int,
    summary_sig_before: tuple[int, int, int],
) -> None:
    """Advance after mutation without a second fragment ``_rerun_ui``."""
    _page()._apply_mapping_advance(
        transcript_path=transcript_path,
        speaker_ids=speaker_ids,
        new_state=new_state,
        speaker_idx=speaker_idx,
        summary_sig_before=summary_sig_before,
    )


def _validate_callback_identity(
    transcript_path: str,
    *,
    expected_speaker_id: str | None = None,
) -> tuple[list[str], int, str] | None:
    """Recompute index + active speaker; return None if identity is stale.

    Thin legacy helper used by tests and as a pre-check for synthesising
    action-service commands. Domain rejection also lives in the action service.
    """
    page = _page()
    try:
        index = page.load_speaker_identification_index(transcript_path)
    except FileNotFoundError:
        _set_flash(
            transcript_path, level="error", message="Transcript file is missing."
        )
        return None
    speaker_ids = list(index.ordered_speaker_ids)
    if not speaker_ids:
        _set_flash(transcript_path, level="error", message="No speakers found.")
        return None
    idx = sanitize_play_index(
        st.session_state.get(speaker_idx_key(transcript_path), 0),
        len(speaker_ids),
    )
    if idx is None:
        idx = 0
    active_id = speaker_ids[idx]
    if expected_speaker_id is not None and active_id != expected_speaker_id:
        _set_flash(
            transcript_path,
            level="warning",
            message="Active speaker changed; action was not applied. Try again.",
        )
        return None
    # Soft-check transcript still readable (signature race handled in loaders).
    try:
        page.transcript_segments_signature(transcript_path)
    except FileNotFoundError:
        _set_flash(
            transcript_path, level="error", message="Transcript file is missing."
        )
        return None
    return speaker_ids, idx, active_id


def _cb_save_name(transcript_path: str, expected_speaker_id: str) -> None:
    """Save name / optional profile-link via shared action service."""
    page = _page()
    identity = page._validate_callback_identity(
        transcript_path, expected_speaker_id=expected_speaker_id
    )
    if identity is None:
        return
    speaker_ids, speaker_idx, active_id = identity
    name = str(
        st.session_state.get(name_widget_key(transcript_path, active_id)) or ""
    ).strip()
    token = str(
        st.session_state.get(link_mode_key(transcript_path, active_id)) or ""
    ).strip()
    link_mode = "none"
    profile_id = None
    if token.startswith("existing:"):
        link_mode = "existing"
        profile_id = token.split(":", 1)[1].strip() or None
    elif token in {"create", "none"}:
        link_mode = token
    link_profile = link_mode in {"create", "existing"}
    controller = get_shared_speaker_studio_controller()
    map_state = controller.get_mapping_status(transcript_path)
    service = page._get_action_service()
    ack = service.execute(
        SpeakerIdCommand(
            action="save_name",
            transcript_id=str(transcript_path),
            action_id=new_action_id(),
            action_seq=int(st.session_state.get("sid_action_seq", 0)) + 1,
            current_speaker_idx=speaker_idx,
            expected_speaker_id=expected_speaker_id,
            transcript_revision=transcript_revision_from_path(transcript_path),
            expected_mapping_revision=mapping_revision_from_state(
                map_state.speaker_map, map_state.ignored_speakers
            ),
            payload={
                "display_name": name,
                "link_profile": link_profile,
                "link_mode": link_mode,
                "profile_id": profile_id,
            },
        )
    )
    st.session_state["sid_action_seq"] = ack.action_seq
    page._apply_ack(
        ack, transcript_path=transcript_path, speaker_count=len(speaker_ids)
    )


def _cb_ignore_toggle(transcript_path: str, expected_speaker_id: str) -> None:
    """Ignore / unignore via shared action service."""
    page = _page()
    identity = page._validate_callback_identity(
        transcript_path, expected_speaker_id=expected_speaker_id
    )
    if identity is None:
        return
    speaker_ids, speaker_idx, _active_id = identity
    controller = get_shared_speaker_studio_controller()
    map_state = controller.get_mapping_status(transcript_path)
    service = page._get_action_service()
    ack = service.execute(
        SpeakerIdCommand(
            action="ignore_toggle",
            transcript_id=str(transcript_path),
            action_id=new_action_id(),
            action_seq=int(st.session_state.get("sid_action_seq", 0)) + 1,
            current_speaker_idx=speaker_idx,
            expected_speaker_id=expected_speaker_id,
            transcript_revision=transcript_revision_from_path(transcript_path),
            expected_mapping_revision=mapping_revision_from_state(
                map_state.speaker_map, map_state.ignored_speakers
            ),
        )
    )
    st.session_state["sid_action_seq"] = ack.action_seq
    page._apply_ack(
        ack, transcript_path=transcript_path, speaker_count=len(speaker_ids)
    )


def _cb_prev(transcript_path: str, expected_speaker_id: str) -> None:
    page = _page()
    identity = page._validate_callback_identity(
        transcript_path, expected_speaker_id=expected_speaker_id
    )
    if identity is None:
        return
    speaker_ids, speaker_idx, _ = identity
    service = page._get_action_service()
    ack = service.execute(
        SpeakerIdCommand(
            action="navigate_prev",
            transcript_id=str(transcript_path),
            action_id=new_action_id(),
            action_seq=int(st.session_state.get("sid_action_seq", 0)) + 1,
            current_speaker_idx=speaker_idx,
            expected_speaker_id=expected_speaker_id,
            transcript_revision=transcript_revision_from_path(transcript_path),
        )
    )
    st.session_state["sid_action_seq"] = ack.action_seq
    page._apply_ack(
        ack, transcript_path=transcript_path, speaker_count=len(speaker_ids)
    )


def _cb_next(transcript_path: str, expected_speaker_id: str) -> None:
    page = _page()
    identity = page._validate_callback_identity(
        transcript_path, expected_speaker_id=expected_speaker_id
    )
    if identity is None:
        return
    speaker_ids, speaker_idx, _ = identity
    service = page._get_action_service()
    ack = service.execute(
        SpeakerIdCommand(
            action="navigate_next",
            transcript_id=str(transcript_path),
            action_id=new_action_id(),
            action_seq=int(st.session_state.get("sid_action_seq", 0)) + 1,
            current_speaker_idx=speaker_idx,
            expected_speaker_id=expected_speaker_id,
            transcript_revision=transcript_revision_from_path(transcript_path),
        )
    )
    st.session_state["sid_action_seq"] = ack.action_seq
    page._apply_ack(
        ack, transcript_path=transcript_path, speaker_count=len(speaker_ids)
    )


def _ccv2_processed_action_key(transcript_path: str | Path) -> str:
    return widget_key(transcript_path, "ccv2_processed_action_id")


def _ccv2_last_ack_key(transcript_path: str | Path) -> str:
    return widget_key(transcript_path, "ccv2_last_ack")


def _apply_ccv2_workspace_command(
    transcript_path: str,
    speaker_ids: list[str],
    speaker_idx: int,
    command: dict,
    *,
    controller: SpeakerStudioController | None = None,
    audio_path=None,
    samples_total: int | None = None,
) -> tuple[bool, dict | None]:
    """Dispatch a CCv2 command once; skip duplicate ``action_id`` replays.

    Returns ``(applied, ack_dict)``. ``applied`` is True only when this call
    executed the command (not an idempotent skip).
    """
    from transcriptx.web.workspaces.speaker_id_bridge import dispatch_workspace_command

    page = _page()
    action_id = str(command.get("action_id") or "")
    processed_key = page._ccv2_processed_action_key(transcript_path)
    ack_key = page._ccv2_last_ack_key(transcript_path)
    if action_id and st.session_state.get(processed_key) == action_id:
        stored = st.session_state.get(ack_key)
        return False, stored if isinstance(stored, dict) else None

    ctrl = controller or get_shared_speaker_studio_controller()

    def _on_load_more(n: int | None) -> None:
        l_key = lines_key(transcript_path)
        increment = int(n) if n is not None else page._LINES_PER_PAGE
        if increment < 1:
            increment = page._LINES_PER_PAGE
        current = sanitize_lines_shown(
            st.session_state.get(l_key, page._LINES_PER_PAGE),
            length=samples_total if samples_total is not None else 10**9,
            default=page._LINES_PER_PAGE,
        )
        limit = samples_total if samples_total is not None else current + increment
        st.session_state[l_key] = min(current + increment, limit)

    service = page._get_action_service()
    ack_dict = dispatch_workspace_command(
        command,
        service=service,
        speaker_ids=speaker_ids,
        current_speaker_idx=speaker_idx,
        apply_ack=lambda ack: page._apply_ack(
            ack,
            transcript_path=transcript_path,
            speaker_count=len(speaker_ids),
        ),
        controller=ctrl,
        transcript_path=str(transcript_path),
        audio_path=audio_path,
        on_load_more=_on_load_more,
    )
    if ack_dict is not None:
        st.session_state[ack_key] = ack_dict
        if action_id:
            st.session_state[processed_key] = action_id
        seq = ack_dict.get("action_seq")
        if isinstance(seq, int):
            st.session_state["sid_action_seq"] = seq
    return True, ack_dict


def _cb_ccv2_command(transcript_path: str) -> None:
    """CCv2 ``on_command_change``: apply navigate/save before the fragment paints.

    Speaker-list clicks use ``setTriggerValue("command", ...)``. Streamlit runs
    this callback before the fragment body, so the next paint must already see
    the jumped speaker — otherwise samples/title stay on the previous speaker
    while clips of that previous speaker still play.
    """
    from transcriptx.web.workspaces.speaker_id_bridge import (
        command_from_workspace_result,
        stable_workspace_key,
    )

    page = _page()
    try:
        result_key = stable_workspace_key(str(Path(transcript_path).resolve()))
    except OSError:
        result_key = stable_workspace_key(str(transcript_path))
    command = command_from_workspace_result(st.session_state.get(result_key))
    if not command:
        return
    try:
        index = page.load_speaker_identification_index(transcript_path)
    except FileNotFoundError:
        return
    speaker_ids = list(index.ordered_speaker_ids)
    if not speaker_ids:
        return
    speaker_idx = page._current_speaker_idx(transcript_path, len(speaker_ids))
    active_id = speaker_ids[speaker_idx] if speaker_ids else ""
    samples_total = (
        len(index.segments_by_speaker.get(active_id, [])) if active_id else None
    )
    playback_ctx = resolve_playback_context(
        get_shared_speaker_studio_controller(), transcript_path
    )
    page._apply_ccv2_workspace_command(
        str(transcript_path),
        speaker_ids,
        speaker_idx,
        command,
        audio_path=getattr(playback_ctx, "audio_path", None),
        samples_total=samples_total,
    )


def _drain_pending_ccv2_command(
    transcript_path: str,
    speaker_ids: list[str],
    speaker_idx: int,
) -> int:
    """Apply a pending CCv2 command from session state before computing active samples."""
    from transcriptx.web.workspaces.speaker_id_bridge import (
        command_from_workspace_result,
        stable_workspace_key,
    )

    page = _page()
    try:
        result_key = stable_workspace_key(str(Path(transcript_path).resolve()))
    except OSError:
        result_key = stable_workspace_key(str(transcript_path))
    command = command_from_workspace_result(st.session_state.get(result_key))
    if not command:
        return speaker_idx
    active_id = speaker_ids[speaker_idx] if speaker_ids else ""
    samples_total = None
    try:
        index = page.load_speaker_identification_index(transcript_path)
        if active_id:
            samples_total = len(index.segments_by_speaker.get(active_id, []))
    except FileNotFoundError:
        pass
    playback_ctx = resolve_playback_context(
        get_shared_speaker_studio_controller(), transcript_path
    )
    page._apply_ccv2_workspace_command(
        str(transcript_path),
        speaker_ids,
        speaker_idx,
        command,
        audio_path=getattr(playback_ctx, "audio_path", None),
        samples_total=samples_total,
    )
    return page._current_speaker_idx(transcript_path, len(speaker_ids))


def _cb_jump_change(transcript_path: str) -> None:
    """Jump selectbox on_change: update canonical index only — do not rewrite jump key."""
    page = _page()
    try:
        index = page.load_speaker_identification_index(transcript_path)
    except FileNotFoundError:
        return
    speaker_ids = list(index.ordered_speaker_ids)
    if not speaker_ids:
        return
    jump = sanitize_play_index(
        st.session_state.get(jump_key(transcript_path)),
        len(speaker_ids),
    )
    if jump is None:
        return
    speaker_idx = page._current_speaker_idx(transcript_path, len(speaker_ids))
    service = page._get_action_service()
    ack = service.execute(
        SpeakerIdCommand(
            action="navigate_jump",
            transcript_id=str(transcript_path),
            action_id=new_action_id(),
            action_seq=int(st.session_state.get("sid_action_seq", 0)) + 1,
            current_speaker_idx=speaker_idx,
            transcript_revision=transcript_revision_from_path(transcript_path),
            payload={"target_idx": jump},
        )
    )
    st.session_state["sid_action_seq"] = ack.action_seq
    # Jump must not rewrite the jump widget key (sync_jump=False on navigate_jump).
    page._apply_ack(
        ack, transcript_path=transcript_path, speaker_count=len(speaker_ids)
    )
