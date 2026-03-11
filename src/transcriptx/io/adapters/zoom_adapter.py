"""
Zoom VTT source adapter.

Handles Zoom VTT exports, which use a **double-line cue text** format: the
speaker name appears on the first text line of each cue, and the spoken
utterance on the second.  This differs from standard VTT (and generic VTT
exports), which put speaker hints either in ``<v Name>`` tags or a single
``Name: text`` line.

Zoom VTT shape::

    WEBVTT

    1
    00:00:00.000 --> 00:00:04.200
    Alice Smith
    Hello everyone, good morning.

    2
    00:00:04.500 --> 00:00:09.100
    Bob Jones
    Thanks Alice. Ready to start?

Priority is 8 — lower number than the generic VTT adapter (10), so the
ZoomAdapter wins any confidence tie with VTTAdapter.  When the double-line
speaker pattern is absent (standard VTT), ZoomAdapter returns 0.0 and
VTTAdapter's score of 1.0 wins cleanly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.intermediate_transcript import IntermediateTurn, IntermediateTranscript
from transcriptx.io.vtt_parser import parse_vtt_timestamp

logger = get_logger()

_TIMESTAMP_LINE = re.compile(
    r"^\s*(\d{1,2}:\d{2}:\d{2}\.\d+)\s*-->\s*(\d{1,2}:\d{2}:\d{2}\.\d+)"
)


class ZoomAdapter:
    source_id: ClassVar[str] = "zoom"
    supported_extensions: ClassVar[tuple[str, ...]] = (".vtt",)
    priority: ClassVar[int] = 8

    def detect_confidence(self, path: Path, content: bytes) -> float:
        # Must start with WEBVTT
        text = content.lstrip(b"\xef\xbb\xbf").lstrip()
        if text[:6].upper() != b"WEBVTT":
            return 0.0

        # Look for the Zoom double-line cue pattern in the first 4 KB:
        # timestamp line → speaker name line → utterance line → blank line
        snippet = content[:4096].decode("utf-8", errors="replace")
        lines = snippet.splitlines()

        ts_indices = [i for i, ln in enumerate(lines) if _TIMESTAMP_LINE.match(ln)]
        if not ts_indices:
            return 0.0

        double_line_count = 0
        for ts_i in ts_indices[:5]:  # check up to 5 cues
            # Collect only lines within the same cue block (stop at blank line)
            after: list[str] = []
            for ln in lines[ts_i + 1 : ts_i + 5]:
                stripped = ln.strip()
                if not stripped:
                    break
                after.append(stripped)

            # Zoom pattern: exactly 2 text lines after the timestamp,
            # where the first is a bare speaker name (no "<v" tag, no ":" in it,
            # not a timestamp itself).
            if (
                len(after) >= 2
                and not after[0].startswith("<")
                and ":" not in after[0]
                and not _TIMESTAMP_LINE.match(after[0])
            ):
                double_line_count += 1

        if double_line_count >= 2:
            return 1.0
        if double_line_count >= 1:
            return 0.7
        return 0.0

    def parse(self, path: Path, content: bytes) -> IntermediateTranscript:
        warnings: List[str] = []
        snippet = content.lstrip(b"\xef\xbb\xbf").decode("utf-8", errors="replace")
        lines = snippet.splitlines()

        turns: List[IntermediateTurn] = []
        i = 0
        turn_index = 0

        # Skip WEBVTT header and any leading blank/header lines
        while i < len(lines) and lines[i].strip().upper() in ("WEBVTT", ""):
            i += 1

        while i < len(lines):
            line = lines[i].strip()

            # Skip blank lines
            if not line:
                i += 1
                continue

            # Skip NOTE / STYLE blocks
            if line.upper().startswith(("NOTE", "STYLE")):
                while i < len(lines) and lines[i].strip():
                    i += 1
                continue

            # Optional cue ID (numeric line before timestamp)
            cue_id: Optional[str] = None
            if line.isdigit() and i + 1 < len(lines) and _TIMESTAMP_LINE.match(
                lines[i + 1].strip()
            ):
                cue_id = line
                i += 1
                line = lines[i].strip()

            ts_match = _TIMESTAMP_LINE.match(line)
            if not ts_match:
                i += 1
                continue

            try:
                start = parse_vtt_timestamp(ts_match.group(1))
                end = parse_vtt_timestamp(ts_match.group(2))
            except ValueError as exc:
                warnings.append(f"Turn {turn_index}: bad timestamp — {exc}")
                i += 1
                continue

            # Collect non-empty text lines after timestamp (until blank line)
            i += 1
            text_lines: List[str] = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1

            if not text_lines:
                continue

            # Zoom double-line format: first line = speaker, second = utterance
            if len(text_lines) >= 2 and ":" not in text_lines[0] and not text_lines[0].startswith("<"):
                speaker: Optional[str] = text_lines[0]
                text = " ".join(text_lines[1:])
            else:
                # Fallback: standard VTT-style single-line with optional "Name: text"
                from transcriptx.io.vtt_parser import extract_speaker_hint, strip_html_tags

                raw = "\n".join(text_lines)
                speaker, cleaned = extract_speaker_hint(raw)
                text = strip_html_tags(cleaned)

            if not text:
                continue

            turns.append(
                IntermediateTurn(
                    text=text,
                    speaker=speaker,
                    start=start,
                    end=end,
                    turn_index=turn_index,
                    raw_turn_id=cue_id,
                )
            )
            turn_index += 1

        return IntermediateTranscript(
            source_tool="zoom",
            source_format="vtt",
            turns=turns,
            source_metadata={"original_path": str(path)},
            warnings=warnings,
        )
