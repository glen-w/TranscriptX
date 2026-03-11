"""
Sembly source adapter.

Handles two Sembly export formats:

  - **JSON**: top-level ``"transcript"`` key containing an array of turns with
    ``speaker_name``, ``start_time``, ``end_time``, and ``words_str``.  All
    other top-level keys (``"summary"``, ``"action_items"``, ``"topics"``,
    ``"participants"``) are discarded — adapter-owned preamble removal.

  - **HTML**: styled HTML with ``<div class="transcript-item">`` blocks
    containing ``<span class="speaker-name">`` and ``<span class="transcript-text">``.
    Timestamps are in ``data-start`` / ``data-end`` attributes.  Everything
    outside ``.transcript-item`` blocks (meeting title, summary, participant
    list, action items) is discarded by the adapter.

Both formats produce the same ``IntermediateTranscript`` with
``source_tool="sembly"``.
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

# ── Sembly JSON markers ───────────────────────────────────────────────────────
_SEMBLY_JSON_KEYS = {"transcript", "participants"}

# ── Sembly HTML markers ───────────────────────────────────────────────────────
_SEMBLY_HTML_MARKER = b"transcript-item"


class SemblyAdapter:
    source_id: ClassVar[str] = "sembly"
    supported_extensions: ClassVar[tuple[str, ...]] = (".json", ".html", ".htm")
    priority: ClassVar[int] = 30

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect_confidence(self, path: Path, content: bytes) -> float:
        ext = path.suffix.lower()

        if ext == ".json":
            return self._detect_json(content)

        if ext in (".html", ".htm"):
            return self._detect_html(content)

        return 0.0

    def _detect_json(self, content: bytes) -> float:
        try:
            data = json.loads(content.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 0.0

        if not isinstance(data, dict):
            return 0.0

        if _SEMBLY_JSON_KEYS.issubset(data.keys()):
            # Check that "transcript" is a non-empty list of dicts with speaker_name
            transcript = data.get("transcript", [])
            if (
                isinstance(transcript, list)
                and transcript
                and isinstance(transcript[0], dict)
                and "speaker_name" in transcript[0]
            ):
                return 0.9

        return 0.0

    def _detect_html(self, content: bytes) -> float:
        if _SEMBLY_HTML_MARKER in content:
            return 0.9
        return 0.0

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse(self, path: Path, content: bytes) -> IntermediateTranscript:
        ext = path.suffix.lower()

        if ext == ".json":
            return self._parse_json(path, content)

        if ext in (".html", ".htm"):
            return self._parse_html(path, content)

        return IntermediateTranscript(
            source_tool="sembly",
            source_format=ext.lstrip("."),
            turns=[],
            source_metadata={"original_path": str(path)},
            warnings=[f"Unsupported Sembly file extension: {ext!r}"],
        )

    def _parse_json(self, path: Path, content: bytes) -> IntermediateTranscript:
        warnings: List[str] = []
        try:
            data: Dict[str, Any] = json.loads(content.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return IntermediateTranscript(
                source_tool="sembly",
                source_format="json",
                turns=[],
                source_metadata={"original_path": str(path)},
                warnings=[f"Failed to parse Sembly JSON: {exc}"],
            )

        # Adapter-owned preamble removal: only iterate data["transcript"]
        raw_turns = data.get("transcript", [])
        participants = data.get("participants", [])
        source_metadata: Dict[str, Any] = {
            "original_path": str(path),
            "participants": participants,
        }
        if "summary" in data:
            source_metadata["summary"] = data["summary"]

        turns = self._turns_from_json(raw_turns, warnings)

        return IntermediateTranscript(
            source_tool="sembly",
            source_format="json",
            turns=turns,
            source_metadata=source_metadata,
            warnings=warnings,
        )

    def _turns_from_json(
        self, raw_turns: List[Any], warnings: List[str]
    ) -> List[IntermediateTurn]:
        turns: List[IntermediateTurn] = []
        for idx, item in enumerate(raw_turns):
            if not isinstance(item, dict):
                warnings.append(f"Turn {idx}: not a dict, skipped")
                continue

            text = item.get("words_str", "").strip()
            if not text:
                text = item.get("text", "").strip()

            speaker: Optional[str] = item.get("speaker_name")
            start = item.get("start_time")
            end = item.get("end_time")
            turn_id = item.get("id")

            turns.append(
                IntermediateTurn(
                    text=text,
                    speaker=speaker,
                    start=float(start) if start is not None else None,
                    end=float(end) if end is not None else None,
                    turn_index=idx,
                    raw_turn_id=str(turn_id) if turn_id is not None else None,
                )
            )
        return turns

    def _parse_html(self, path: Path, content: bytes) -> IntermediateTranscript:
        warnings: List[str] = []
        try:
            from bs4 import BeautifulSoup  # type: ignore[import-untyped]
        except ImportError:
            return IntermediateTranscript(
                source_tool="sembly",
                source_format="html",
                turns=[],
                source_metadata={"original_path": str(path)},
                warnings=["beautifulsoup4 is required to parse Sembly HTML exports"],
            )

        try:
            html = content.decode("utf-8", errors="replace")
            soup = BeautifulSoup(html, "html.parser")
        except Exception as exc:
            return IntermediateTranscript(
                source_tool="sembly",
                source_format="html",
                turns=[],
                source_metadata={"original_path": str(path)},
                warnings=[f"Failed to parse Sembly HTML: {exc}"],
            )

        # Adapter-owned preamble removal: only select .transcript-item blocks
        items = soup.select(".transcript-item")
        if not items:
            warnings.append("No .transcript-item elements found in Sembly HTML")

        turns: List[IntermediateTurn] = []
        for idx, item in enumerate(items):
            speaker_tag = item.select_one(".speaker-name")
            text_tag = item.select_one(".transcript-text")

            speaker = speaker_tag.get_text(strip=True) if speaker_tag else None
            text = (
                text_tag.get_text(strip=True) if text_tag else item.get_text(strip=True)
            )

            start_raw = item.get("data-start")
            end_raw = item.get("data-end")

            try:
                start: Optional[float] = float(start_raw) if start_raw else None
            except (ValueError, TypeError):
                start = None
                warnings.append(f"Turn {idx}: could not parse data-start={start_raw!r}")

            try:
                end: Optional[float] = float(end_raw) if end_raw else None
            except (ValueError, TypeError):
                end = None
                warnings.append(f"Turn {idx}: could not parse data-end={end_raw!r}")

            if not text:
                warnings.append(f"Turn {idx}: empty text, skipped")
                continue

            turns.append(
                IntermediateTurn(
                    text=text,
                    speaker=speaker,
                    start=start,
                    end=end,
                    turn_index=idx,
                )
            )

        return IntermediateTranscript(
            source_tool="sembly",
            source_format="html",
            turns=turns,
            source_metadata={"original_path": str(path)},
            warnings=warnings,
        )
