"""
VTT source adapter.

Wraps the existing vtt_parser module and converts VTTCue objects into the
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
from transcriptx.io.vtt_parser import _parse_vtt_lines

logger = get_logger()


class VTTAdapter:
    source_id: ClassVar[str] = "vtt"
    supported_extensions: ClassVar[tuple[str, ...]] = (".vtt",)
    priority: ClassVar[int] = 10

    def detect_confidence(self, path: Path, content: bytes) -> float:
        # VTT files begin with "WEBVTT" (possibly after a UTF-8 BOM)
        text = content.lstrip(b"\xef\xbb\xbf").lstrip()
        if text[:6].upper() == b"WEBVTT":
            return 1.0
        return 0.0

    def parse(self, path: Path, content: bytes) -> IntermediateTranscript:
        warnings: List[str] = []
        try:
            lines = (
                content.lstrip(b"\xef\xbb\xbf")
                .decode("utf-8", errors="replace")
                .splitlines(keepends=True)
            )
            cues = _parse_vtt_lines(lines)
        except Exception as exc:
            return IntermediateTranscript(
                source_tool="vtt",
                source_format="vtt",
                turns=[],
                source_metadata={"original_path": str(path)},
                warnings=[f"Failed to parse VTT: {exc}"],
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
                    raw=cue.raw_text,
                )
            )

        return IntermediateTranscript(
            source_tool="vtt",
            source_format="vtt",
            turns=turns,
            source_metadata={"original_path": str(path)},
            warnings=warnings,
        )
