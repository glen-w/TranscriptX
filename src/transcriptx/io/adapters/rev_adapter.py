"""
Rev.com source adapter.

Handles Rev.com JSON transcript exports.  The transcript content lives under
``monologues`` — each monologue contains an ``elements`` array whose ``"text"``
entries are concatenated into the utterance.

Rev JSON shape::

    {
      "monologues": [
        {
          "speaker": 0,
          "start_time": 0.0,
          "end_time": 4.2,
          "elements": [
            {"type": "text", "value": "Hello everyone."},
            {"type": "punct", "value": " "}
          ]
        }, ...
      ]
    }

Speaker labels in Rev are integer indices.  They are converted to strings
(``"0"``, ``"1"``, …) in the intermediate model; ``SpeakerNormalizer`` will
map them to ``SPEAKER_XX`` format.
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


class RevAdapter:
    source_id: ClassVar[str] = "rev"
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

        monologues = data.get("monologues")
        if isinstance(monologues, list) and monologues:
            first = monologues[0]
            if isinstance(first, dict) and "elements" in first and "speaker" in first:
                return 0.9

        return 0.0

    def parse(self, path: Path, content: bytes) -> IntermediateTranscript:
        warnings: List[str] = []
        try:
            data: Dict[str, Any] = json.loads(content.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return IntermediateTranscript(
                source_tool="rev",
                source_format="json",
                turns=[],
                source_metadata={"original_path": str(path)},
                warnings=[f"Failed to parse Rev JSON: {exc}"],
            )

        raw_monologues: List[Any] = data.get("monologues", [])

        turns: List[IntermediateTurn] = []
        for idx, mono in enumerate(raw_monologues):
            if not isinstance(mono, dict):
                warnings.append(f"Monologue {idx}: not a dict, skipped")
                continue

            # Concatenate text elements (skip punct-only elements if mixed)
            elements: List[Dict[str, Any]] = mono.get("elements", [])
            text_parts = [
                e["value"]
                for e in elements
                if isinstance(e, dict) and e.get("type") == "text"
            ]
            text = " ".join(text_parts).strip()
            if not text:
                # Fallback: concatenate all values
                text = "".join(
                    e.get("value", "") for e in elements if isinstance(e, dict)
                ).strip()

            speaker_raw = mono.get("speaker")
            speaker = str(speaker_raw) if speaker_raw is not None else None

            start = mono.get("start_time")
            end = mono.get("end_time")

            turns.append(
                IntermediateTurn(
                    text=text,
                    speaker=speaker,
                    start=float(start) if start is not None else None,
                    end=float(end) if end is not None else None,
                    turn_index=idx,
                    raw_turn_id=str(idx),
                )
            )

        return IntermediateTranscript(
            source_tool="rev",
            source_format="json",
            turns=turns,
            source_metadata={"original_path": str(path)},
            warnings=warnings,
        )
