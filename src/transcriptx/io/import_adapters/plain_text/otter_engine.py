"""
Otter.ai source adapter.

Handles Otter.ai JSON exports.  The transcript content lives under
``speech_segments`` — all other top-level keys (``title``, ``summary``,
``created_at``) are discarded (adapter-owned preamble removal).

Otter JSON shape::

    {
      "title": "...",
      "speech_segments": [
        {
          "speaker_id": 0,
          "speaker_name": "Alice",
          "start_ts": 0.0,
          "end_ts": 4.3,
          "transcript": "utterance text"
        }, ...
      ]
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

_OTTER_KEYS = {"speech_segments"}


class OtterAdapter:
    source_id: ClassVar[str] = "otter"
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

        segs = data.get("speech_segments")
        if isinstance(segs, list) and segs:
            first = segs[0]
            if isinstance(first, dict) and "transcript" in first:
                return 0.9

        return 0.0

    def parse(self, path: Path, content: bytes) -> IntermediateTranscript:
        warnings: List[str] = []
        try:
            data: Dict[str, Any] = json.loads(content.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return IntermediateTranscript(
                source_tool="otter",
                source_format="json",
                turns=[],
                source_metadata={"original_path": str(path)},
                warnings=[f"Failed to parse Otter JSON: {exc}"],
            )

        # Adapter-owned preamble removal: only iterate speech_segments
        raw_segs: List[Any] = data.get("speech_segments", [])
        source_metadata: Dict[str, Any] = {
            "original_path": str(path),
            "title": data.get("title"),
        }

        turns: List[IntermediateTurn] = []
        for idx, seg in enumerate(raw_segs):
            if not isinstance(seg, dict):
                warnings.append(f"Segment {idx}: not a dict, skipped")
                continue

            text = seg.get("transcript", "").strip()
            speaker = seg.get("speaker_name") or str(seg.get("speaker_id", ""))
            start = seg.get("start_ts")
            end = seg.get("end_ts")

            turns.append(
                IntermediateTurn(
                    text=text,
                    speaker=speaker if speaker else None,
                    start=float(start) if start is not None else None,
                    end=float(end) if end is not None else None,
                    turn_index=idx,
                    raw_turn_id=str(seg.get("speaker_id", idx)),
                )
            )

        return IntermediateTranscript(
            source_tool="otter",
            source_format="json",
            turns=turns,
            source_metadata=source_metadata,
            warnings=warnings,
        )
