"""Apply SpeakerIdAck effects to the legacy Streamlit Speaker ID session."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from transcriptx.app.speaker_id.protocol import SpeakerIdAck


def apply_speaker_id_ack_effects(
    ack: SpeakerIdAck,
    *,
    transcript_path: str | Path,
    speaker_count: int,
    set_flash: Callable[..., None],
    navigate_to_speaker: Callable[..., int],
    sync_jump_widget: Callable[..., None],
    invalidate_transcript_summary_for_path: Callable[..., None],
    consume_cache_invalidation_signal: Callable[..., None],
    rerun_app_for_completion: Callable[[], None],
    session_state: dict,
    clear_playback_session_keys: Optional[Callable[..., None]] = None,
) -> None:
    """Translate an acknowledgement into legacy session mutations.

    Requests a full-app completion refresh via ``rerun_app_for_completion`` when
    the ack asks for one. The page adapter must only set a flag from callbacks;
    the fragment body performs the app rerun.
    """
    effects = ack.effects
    if effects.cache_invalidation_signal is not None:
        consume_cache_invalidation_signal(effects.cache_invalidation_signal)
    if effects.invalidate_summary_sig is not None:
        invalidate_transcript_summary_for_path(
            transcript_path, signature=effects.invalidate_summary_sig
        )
    for flash in effects.flashes:
        set_flash(transcript_path, level=flash.level, message=flash.message)
    if effects.navigate_to_idx is not None:
        idx = navigate_to_speaker(
            effects.navigate_to_idx,
            transcript_path=transcript_path,
            speaker_count=speaker_count,
        )
        if effects.sync_jump:
            sync_jump_widget(idx, transcript_path=transcript_path)
        session_state["speaker_id_speaker_idx"] = idx
    if effects.requires_app_rerun:
        rerun_app_for_completion()
