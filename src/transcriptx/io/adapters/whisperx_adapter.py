"""
WhisperX source adapter.

TranscriptX's primary native JSON source.  Handles three WhisperX input shapes:

  1. Standard — ``{"segments": [{…, "speaker": "SPEAKER_00", …}, …]}``
  2. Word-level — ``{"segments": [{…, "words": [{…, "speaker": "SPEAKER_00"}, …]}]}``
     Speaker is promoted from the most-common word-level speaker per segment.
  3. Legacy bare-list — ``[{…}, …]``

WhisperXAdapter is an explicit structured JSON adapter with dedicated detection
logic.  It is TranscriptX's primary JSON workflow and is *not* the fallback for
unknown or unrecognised JSON.  A ``.json`` file that matches no adapter's
confidence threshold must raise ``UnsupportedFormatError``; there is no implicit
WhisperX default.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.intermediate_transcript import (
    IntermediateTurn,
    IntermediateTranscript,
)

logger = get_logger()

# Keys considered definitive WhisperX structural markers
_WHISPERX_SEGMENT_KEYS = {"start", "end", "text"}
_WHISPERX_WORD_KEYS = {"word", "start", "end"}


def _most_common_speaker(words: List[Dict[str, Any]]) -> Optional[str]:
    counts: Dict[str, int] = {}
    for w in words:
        if isinstance(w, dict):
            spk = w.get("speaker")
            if spk:
                counts[spk] = counts.get(spk, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.__getitem__)


def _looks_like_whisperx_segments(segments: Any) -> bool:
    """Return True if segments is a list of dicts with WhisperX-shaped entries."""
    if not isinstance(segments, list) or not segments:
        return False
    sample = segments[0]
    return isinstance(sample, dict) and _WHISPERX_SEGMENT_KEYS.issubset(sample.keys())


class WhisperXAdapter:
    source_id: ClassVar[str] = "whisperx"
    supported_extensions: ClassVar[tuple[str, ...]] = (".json",)
    priority: ClassVar[int] = 20

    def detect_confidence(self, path: Path, content: bytes) -> float:
        try:
            data = json.loads(content.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 0.0

        # Already-normalised TranscriptX artifact — not raw WhisperX
        if isinstance(data, dict) and "schema_version" in data and "source" in data:
            return 0.0

        # Shape 1 / 2: {"segments": [...]}
        if isinstance(data, dict):
            segs = data.get("segments")
            if _looks_like_whisperx_segments(segs):
                return 0.9

        # Shape 3: bare list
        if isinstance(data, list) and _looks_like_whisperx_segments(data):
            return 0.8

        return 0.0

    def parse(self, path: Path, content: bytes) -> IntermediateTranscript:
        warnings: List[str] = []
        try:
            data = json.loads(content.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return IntermediateTranscript(
                source_tool="whisperx",
                source_format="json",
                turns=[],
                source_metadata={"original_path": str(path)},
                warnings=[f"Failed to decode JSON: {exc}"],
            )

        # Normalise to a list of raw segment dicts
        if isinstance(data, dict):
            raw_segments: List[Dict[str, Any]] = data.get("segments", [])
        elif isinstance(data, list):
            raw_segments = data
        else:
            return IntermediateTranscript(
                source_tool="whisperx",
                source_format="json",
                turns=[],
                source_metadata={"original_path": str(path)},
                warnings=["Unrecognised WhisperX JSON shape; no segments extracted"],
            )

        turns: List[IntermediateTurn] = []
        for idx, seg in enumerate(raw_segments):
            if not isinstance(seg, dict):
                warnings.append(f"Segment {idx}: not a dict, skipped")
                continue

            text = seg.get("text", "")
            start = seg.get("start")
            end = seg.get("end")

            # Determine speaker
            speaker: Optional[str] = seg.get("speaker")
            words: Optional[List[Dict[str, Any]]] = seg.get("words")

            if speaker is None and words:
                promoted = _most_common_speaker(words)
                if promoted:
                    speaker = promoted
                else:
                    warnings.append(f"Segment {idx}: no speaker found in words array")

            turns.append(
                IntermediateTurn(
                    text=text,
                    speaker=speaker,
                    start=float(start) if start is not None else None,
                    end=float(end) if end is not None else None,
                    turn_index=idx,
                    raw_turn_id=str(idx),
                    words=words,
                )
            )

        return IntermediateTranscript(
            source_tool="whisperx",
            source_format="json",
            turns=turns,
            source_metadata={"original_path": str(path)},
            warnings=warnings,
        )
