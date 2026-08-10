"""PlaybackHost contract for Theme D handoff (Theme C Phase 7).

Persistent player API shared by Speaker ID CCv2 and future karaoke/reader
surfaces. Does not invent word timings — consumers must check
``has_word_timestamps`` on canonical transcripts and degrade gracefully.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class PlaybackHostCapabilities:
    persistent_audio_element: bool = True
    seek_api: bool = True
    local_clock_only: bool = True  # never stream current_time via setStateValue
    word_timing_ready: bool = False  # Theme D fills this from transcript capability


class PlaybackHost(Protocol):
    """Minimal host surface Theme D can bind to."""

    def play_clip(self, clip_id: str, src: str) -> None: ...

    def pause(self) -> None: ...

    def seek_ms(self, position_ms: int) -> None: ...

    def local_current_time_ms(self) -> int:
        """Browser-local playhead; must not be mirrored continuously to Python."""
        ...

    def capabilities(self) -> PlaybackHostCapabilities: ...


def word_timing_capability(has_word_timestamps: bool) -> PlaybackHostCapabilities:
    """Build capabilities without inventing timings when absent."""
    return PlaybackHostCapabilities(
        word_timing_ready=bool(has_word_timestamps),
    )
