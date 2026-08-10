"""Clip-relative word timings for Theme D karaoke playback.

Never invents timings. Degrades to segment-level when ``words[]`` are missing,
unaligned, or lack usable start/end after clip rebasing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from transcriptx.core.corrections.word_spans import WordSpan, iter_segment_word_spans
from transcriptx.services.speaker_studio.clip_service import MAX_CLIP_DURATION_SEC
from transcriptx.web.workspaces.playback_host import (
    PlaybackHostCapabilities,
    word_timing_capability,
)

# Minimum fraction of tokens with usable timings to enable word karaoke.
_KARAOKE_COVERAGE_FLOOR = 0.35
# Absolute epsilon when comparing relative bounds (seconds).
_TIME_EPS = 1e-3


@dataclass(frozen=True)
class KaraokeWord:
    """One display token with optional clip-relative timings (seconds)."""

    text: str
    char_start: int
    char_end: int
    t0: Optional[float] = None
    t1: Optional[float] = None

    @property
    def timed(self) -> bool:
        return self.t0 is not None and self.t1 is not None


@dataclass(frozen=True)
class KaraokeClipModel:
    """Payload for the browser-local karaoke player (one clip)."""

    mode: str  # "karaoke" | "segment"
    text: str
    speaker: str
    clip_start: float
    clip_end: float
    playable_duration: float
    words: tuple[KaraokeWord, ...]
    timed_word_count: int
    capabilities: PlaybackHostCapabilities

    @property
    def word_timing_ready(self) -> bool:
        return self.mode == "karaoke" and self.capabilities.word_timing_ready


def _speaker_label(segment: Mapping[str, Any]) -> str:
    display = segment.get("speaker_display")
    if display is not None and str(display).strip():
        return str(display).strip()
    speaker = segment.get("speaker")
    if speaker is not None and str(speaker).strip():
        return str(speaker).strip()
    return "Unknown"


def _clip_window(segment_start: float, segment_end: float) -> tuple[float, float, float]:
    """Return (clip_start, clip_end, playable_duration) capped like ClipService."""
    start = float(segment_start)
    end = float(segment_end)
    if end <= start:
        return start, start, 0.0
    playable_end = min(end, start + float(MAX_CLIP_DURATION_SEC))
    return start, playable_end, max(0.0, playable_end - start)


def _rebase_span(
    span: WordSpan,
    *,
    clip_start: float,
    playable_duration: float,
) -> KaraokeWord:
    """Map absolute word times into clip-relative seconds; drop invalid timings."""
    t0 = span.start
    t1 = span.end
    if t0 is None or t1 is None:
        return KaraokeWord(
            text=span.text,
            char_start=span.char_start,
            char_end=span.char_end,
        )
    rel0 = float(t0) - clip_start
    rel1 = float(t1) - clip_start
    if not (rel1 > rel0):
        return KaraokeWord(
            text=span.text,
            char_start=span.char_start,
            char_end=span.char_end,
        )
    # Entirely outside the playable window → keep text, no timings.
    if rel1 <= 0.0 + _TIME_EPS or rel0 >= playable_duration - _TIME_EPS:
        return KaraokeWord(
            text=span.text,
            char_start=span.char_start,
            char_end=span.char_end,
        )
    rel0 = max(0.0, rel0)
    rel1 = min(playable_duration, rel1)
    if rel1 <= rel0:
        return KaraokeWord(
            text=span.text,
            char_start=span.char_start,
            char_end=span.char_end,
        )
    return KaraokeWord(
        text=span.text,
        char_start=span.char_start,
        char_end=span.char_end,
        t0=rel0,
        t1=rel1,
    )


def _whitespace_tokens(text: str) -> tuple[KaraokeWord, ...]:
    words: list[KaraokeWord] = []
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        j = i
        while j < n and not text[j].isspace():
            j += 1
        words.append(KaraokeWord(text=text[i:j], char_start=i, char_end=j))
        i = j
    return tuple(words)


def build_karaoke_clip_model(
    segment: Mapping[str, Any],
    *,
    clip_start: Optional[float] = None,
    clip_end: Optional[float] = None,
) -> KaraokeClipModel:
    """Build a karaoke model from a canonical segment dict.

    ``clip_start`` / ``clip_end`` default to the segment bounds (then capped).
    """
    text = segment.get("text")
    if text is None:
        text = ""
    elif not isinstance(text, str):
        text = str(text)

    seg_start = segment.get("start", 0.0)
    seg_end = segment.get("end", 0.0)
    try:
        start_f = float(clip_start if clip_start is not None else seg_start)
        end_f = float(clip_end if clip_end is not None else seg_end)
    except (TypeError, ValueError):
        start_f, end_f = 0.0, 0.0

    c_start, c_end, duration = _clip_window(start_f, end_f)
    spans, aligned = iter_segment_word_spans(dict(segment))
    if not spans:
        words = _whitespace_tokens(text)
    else:
        words = tuple(
            _rebase_span(span, clip_start=c_start, playable_duration=duration)
            for span in spans
        )

    timed_count = sum(1 for w in words if w.timed)
    total = len(words)
    coverage = (timed_count / total) if total else 0.0
    # Only enable karaoke when alignment succeeded and coverage is honest.
    karaoke_ok = (
        aligned
        and duration > 0.0
        and timed_count > 0
        and coverage >= _KARAOKE_COVERAGE_FLOOR
    )
    caps = word_timing_capability(karaoke_ok)
    return KaraokeClipModel(
        mode="karaoke" if karaoke_ok else "segment",
        text=text,
        speaker=_speaker_label(segment),
        clip_start=c_start,
        clip_end=c_end,
        playable_duration=duration,
        words=words,
        timed_word_count=timed_count,
        capabilities=caps,
    )


def karaoke_words_payload(model: KaraokeClipModel) -> list[dict[str, Any]]:
    """JSON-serialisable word list for the browser player."""
    out: list[dict[str, Any]] = []
    for w in model.words:
        item: dict[str, Any] = {"t": w.text}
        if w.timed:
            item["t0"] = round(float(w.t0), 3)  # type: ignore[arg-type]
            item["t1"] = round(float(w.t1), 3)  # type: ignore[arg-type]
        out.append(item)
    return out


def segment_dict_for_source(
    segments: Sequence[Mapping[str, Any]],
    source_index: int,
) -> Optional[Mapping[str, Any]]:
    """Return the segment mapping at ``source_index`` when in range."""
    if source_index < 0 or source_index >= len(segments):
        return None
    seg = segments[source_index]
    return seg if isinstance(seg, Mapping) else None
