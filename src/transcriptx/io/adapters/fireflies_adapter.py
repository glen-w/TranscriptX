"""
Fireflies.ai source adapter.

Handles Fireflies.ai JSON exports.  The transcript content lives under
``meeting.sentences`` — all other top-level keys (``meeting.summary``,
``meeting.title``, ``meeting.date``) are discarded (adapter-owned preamble
removal).

Fireflies JSON shape::

    {
      "meeting": {
        "id": "...",
        "title": "...",
        "sentences": [
          {
            "index": 0,
            "speaker_id": "spk_alice",
            "speaker_name": "Alice",
            "start_time": 0.0,
            "end_time": 4.2,
            "text": "utterance text"
          }, ...
        ]
      }
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar, Dict, List

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.intermediate_transcript import (
    IntermediateTurn,
    IntermediateTranscript,
)

logger = get_logger()


class FirefliesAdapter:
    source_id: ClassVar[str] = "fireflies"
    supported_extensions: ClassVar[tuple[str, ...]] = (".json",)
    priority: ClassVar[int] = 40

    def detect_confidence(self, path: Path, content: bytes) -> float:
        try:
            data = json.loads(content.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 0.0

        if not isinstance(data, dict):
            return 0.0
        if "schema_version" in data and "source" in data:
            return 0.0

        meeting = data.get("meeting")
        if isinstance(meeting, dict):
            sentences = meeting.get("sentences")
            if isinstance(sentences, list) and sentences:
                first = sentences[0]
                if (
                    isinstance(first, dict)
                    and "text" in first
                    and "start_time" in first
                ):
                    return 0.9

        return 0.0

    def parse(self, path: Path, content: bytes) -> IntermediateTranscript:
        warnings: List[str] = []
        try:
            data: Dict[str, Any] = json.loads(content.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return IntermediateTranscript(
                source_tool="fireflies",
                source_format="json",
                turns=[],
                source_metadata={"original_path": str(path)},
                warnings=[f"Failed to parse Fireflies JSON: {exc}"],
            )

        meeting: Dict[str, Any] = data.get("meeting", {})
        # Adapter-owned preamble removal: only iterate meeting.sentences
        raw_sentences: List[Any] = meeting.get("sentences", [])
        source_metadata: Dict[str, Any] = {
            "original_path": str(path),
            "title": meeting.get("title"),
            "meeting_id": meeting.get("id"),
        }

        turns: List[IntermediateTurn] = []
        for idx, sent in enumerate(raw_sentences):
            if not isinstance(sent, dict):
                warnings.append(f"Sentence {idx}: not a dict, skipped")
                continue

            text = sent.get("text", "").strip()
            speaker = sent.get("speaker_name") or sent.get("speaker_id")
            start = sent.get("start_time")
            end = sent.get("end_time")
            sent_id = sent.get("index", idx)

            turns.append(
                IntermediateTurn(
                    text=text,
                    speaker=str(speaker) if speaker else None,
                    start=float(start) if start is not None else None,
                    end=float(end) if end is not None else None,
                    turn_index=idx,
                    raw_turn_id=str(sent_id),
                )
            )

        return IntermediateTranscript(
            source_tool="fireflies",
            source_format="json",
            turns=turns,
            source_metadata=source_metadata,
            warnings=warnings,
        )
