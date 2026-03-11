"""
SRT source adapter.

Wraps the existing srt_parser module and converts SRTCue objects into the
canonical IntermediateTranscript model.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, List

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.intermediate_transcript import (
    IntermediateTurn,
    IntermediateTranscript,
)
from transcriptx.io.srt_parser import _parse_srt_lines

logger = get_logger()


class SRTAdapter:
    source_id: ClassVar[str] = "srt"
    supported_extensions: ClassVar[tuple[str, ...]] = (".srt",)
    priority: ClassVar[int] = 10

    def detect_confidence(self, path: Path, content: bytes) -> float:
        # SRT files: numeric cue ID on first non-empty line, followed by a
        # timestamp line with "-->".  Check for the pattern in the first 4 KB.
        try:
            text = content.lstrip(b"\xef\xbb\xbf").decode("utf-8", errors="replace")
        except Exception:
            return 0.0

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for i, line in enumerate(lines[:10]):
            if line.isdigit() and i + 1 < len(lines) and "-->" in lines[i + 1]:
                return 1.0
            if "-->" in line and "," in line:
                # SRT timestamps use comma as millisecond separator
                return 0.9
        return 0.0

    def parse(self, path: Path, content: bytes) -> IntermediateTranscript:
        warnings: List[str] = []
        try:
            lines = (
                content.lstrip(b"\xef\xbb\xbf")
                .decode("utf-8", errors="replace")
                .splitlines()
            )
            lines = [ln.rstrip("\r") for ln in lines]
            cues = _parse_srt_lines(lines)
        except Exception as exc:
            return IntermediateTranscript(
                source_tool="srt",
                source_format="srt",
                turns=[],
                source_metadata={"original_path": str(path)},
                warnings=[f"Failed to parse SRT: {exc}"],
            )

        turns: List[IntermediateTurn] = []
        for idx, cue in enumerate(cues):
            turns.append(
                IntermediateTurn(
                    text=cue.text,
                    speaker=cue.speaker_hint,
                    start=cue.start,
                    end=cue.end,
                    turn_index=idx,
                    raw_turn_id=cue.id,
                    raw=None,
                )
            )

        return IntermediateTranscript(
            source_tool="srt",
            source_format="srt",
            turns=turns,
            source_metadata={"original_path": str(path)},
            warnings=warnings,
        )
