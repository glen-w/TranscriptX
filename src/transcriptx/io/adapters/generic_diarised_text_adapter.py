"""
Generic diarised-text adapter — universal fallback.

Handles semi-structured plain-text transcripts that follow the common pattern::

    Speaker Name: utterance text

or with an optional timestamp prefix::

    [HH:MM:SS] Speaker Name: utterance text
    [MM:SS] Speaker Name: utterance text
    00:01:23 Speaker Name: utterance text

Evaluated last (``priority=1000``) after all specific adapters have had a chance
to claim the file.

Binary-file guard: ``detect_confidence()`` first attempts to UTF-8 decode the
first 4 KB of content.  If the bytes are not plausibly text-decodable (NUL bytes,
high non-UTF8 byte density), it returns ``0.0`` immediately to prevent false
positives on ``.docx``, ``.pdf``, or other binary blobs with unknown extensions.

Skips leading lines before the first ``Speaker: text`` match (adapter-owned
preamble removal for generic meeting notes that have a header block).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.intermediate_transcript import IntermediateTurn, IntermediateTranscript

logger = get_logger()

# ── Pattern helpers ───────────────────────────────────────────────────────────

# Optional timestamp prefixes
_TS_HHMMSS = r"(?:\[?(\d{1,2}:\d{2}:\d{2}(?:\.\d+)?)\]?\s*)?"
_TS_MMSS = r"(?:\[?(\d{1,2}:\d{2}(?:\.\d+)?)\]?\s*)?"

# Speaker label: starts with a capital letter, 1-60 chars, no newlines
_SPEAKER_PAT = r"([A-Z][^\n:]{0,59}?)"

# Full line pattern (timestamp optional, speaker required, colon separator)
_TURN_LINE = re.compile(
    r"^\s*(?:\[?(\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)\]?\s+)?"  # optional timestamp
    r"([A-Z][^\n:]{0,59}?)"                                       # speaker
    r":\s+"                                                        # colon separator
    r"(.+)$",                                                      # utterance
    re.IGNORECASE,
)


def _parse_timestamp(ts: Optional[str]) -> Optional[float]:
    """Convert HH:MM:SS or MM:SS (or with fractional seconds) to seconds."""
    if ts is None:
        return None
    ts = ts.strip("[] ")
    parts = ts.split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
    except (ValueError, TypeError):
        pass
    return None


def _is_plausibly_text(content: bytes) -> bool:
    """Return True if *content* looks like UTF-8 or ASCII text.

    Rejects content with NUL bytes or a high density of non-ASCII non-UTF8 bytes
    (>20% of the sample), which indicates binary format (.docx zip, .pdf, etc.).
    """
    if b"\x00" in content:
        return False

    try:
        content.decode("utf-8")
        return True
    except UnicodeDecodeError:
        pass

    # Fallback: count high-range bytes (>0x7F) in a latin-1 decode
    high_bytes = sum(1 for b in content if b > 0x7F)
    if high_bytes / max(len(content), 1) > 0.20:
        return False

    return True


class GenericDiarisedTextAdapter:
    source_id: ClassVar[str] = "generic_text"
    supported_extensions: ClassVar[tuple[str, ...]] = (".txt", ".text", ".transcript")
    priority: ClassVar[int] = 1000

    def detect_confidence(self, path: Path, content: bytes) -> float:
        # Binary-file guard: reject non-text content immediately
        if not _is_plausibly_text(content):
            return 0.0

        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            return 0.0

        lines = text.splitlines()
        matches = sum(1 for line in lines if _TURN_LINE.match(line))

        if not lines:
            return 0.0

        ratio = matches / len(lines)
        if ratio >= 0.5:
            return 0.8
        if matches >= 3:
            return 0.5
        if matches >= 1:
            return 0.3
        return 0.0

    def parse(self, path: Path, content: bytes) -> IntermediateTranscript:
        warnings: List[str] = []

        if not _is_plausibly_text(content):
            return IntermediateTranscript(
                source_tool="generic_text",
                source_format="txt",
                turns=[],
                source_metadata={"original_path": str(path)},
                warnings=["Content does not appear to be text; refusing to parse"],
            )

        try:
            text = content.decode("utf-8", errors="replace")
        except Exception as exc:
            return IntermediateTranscript(
                source_tool="generic_text",
                source_format="txt",
                turns=[],
                source_metadata={"original_path": str(path)},
                warnings=[f"Failed to decode text: {exc}"],
            )

        turns = self._extract_turns(text, warnings)

        return IntermediateTranscript(
            source_tool="generic_text",
            source_format="txt",
            turns=turns,
            source_metadata={"original_path": str(path)},
            warnings=warnings,
        )

    def _extract_turns(self, text: str, warnings: List[str]) -> List[IntermediateTurn]:
        lines = text.splitlines()
        turns: List[IntermediateTurn] = []
        turn_index = 0
        found_first = False

        for line_no, line in enumerate(lines, start=1):
            m = _TURN_LINE.match(line)
            if not m:
                if not found_first:
                    continue  # preamble before first match — skip
                # Could be continuation of previous turn; ignore for now
                continue

            found_first = True
            ts_raw = m.group(1)
            speaker = m.group(2).strip()
            utterance = m.group(3).strip()

            start = _parse_timestamp(ts_raw)

            turns.append(
                IntermediateTurn(
                    text=utterance,
                    speaker=speaker if speaker else None,
                    start=start,
                    end=None,    # no end time in diarised-text format
                    turn_index=turn_index,
                    raw=line,
                )
            )
            turn_index += 1

        if not turns:
            warnings.append("No diarised turns found in text file")

        return turns
