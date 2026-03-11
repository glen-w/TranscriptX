"""
Transcript normalizer — structural repair only.

Receives an IntermediateTranscript whose turns are already free of vendor
preamble (adapters removed it).  Performs:

  - End-timestamp repair (fills missing ``end`` values)
  - Optional same-speaker turn merging (disabled by default)
  - Speaker label cleaning (strip trailing colons, embedded timestamps, etc.)
  - Overlap/gap warnings (non-fatal)

Does NOT know anything about vendor-specific preamble patterns.  That knowledge
lives exclusively in the adapters.
"""

from __future__ import annotations

import re
import statistics
from typing import List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.intermediate_transcript import (
    IntermediateTurn,
    IntermediateTranscript,
)

logger = get_logger()

# Default estimated duration when next-turn start is unavailable
_DEFAULT_ESTIMATED_DURATION_S = 5.0

# Speaker labels that should be treated as absent
_NULL_SPEAKER_PATTERNS = re.compile(
    r"^(unknown\s*speaker|speaker\s*\?|n/?a|\?+|none|—|-)$",
    re.IGNORECASE,
)

# Patterns to strip from speaker labels (trailing colon, embedded timestamps)
_TRAILING_COLON = re.compile(r":+\s*$")
_EMBEDDED_TIMESTAMP = re.compile(r"\[\d{1,2}:\d{2}(:\d{2})?\]")


class TranscriptNormalizer:
    """Structural repair normalizer for IntermediateTranscript.

    Args:
        merge_same_speaker: Join consecutive same-speaker turns with no gap.
            Default ``False``.
        default_estimated_duration: Fallback duration in seconds when end time
            cannot be derived from the next turn.  Default ``5.0``.
        gap_warning_threshold_s: Warn (non-fatal) when consecutive turns have a
            gap larger than this value.  Default ``30.0``.
    """

    def __init__(
        self,
        merge_same_speaker: bool = False,
        default_estimated_duration: float = _DEFAULT_ESTIMATED_DURATION_S,
        gap_warning_threshold_s: float = 30.0,
    ) -> None:
        self.merge_same_speaker = merge_same_speaker
        self.default_estimated_duration = default_estimated_duration
        self.gap_warning_threshold_s = gap_warning_threshold_s

    def normalize(self, transcript: IntermediateTranscript) -> List[IntermediateTurn]:
        """Return a repaired list of IntermediateTurn objects.

        Warnings are appended to ``transcript.warnings`` in-place so callers
        can inspect them after normalisation.
        """
        turns = list(transcript.turns)

        turns = self._clean_speaker_labels(turns, transcript.warnings)
        turns = self._repair_end_timestamps(turns, transcript.warnings)

        if self.merge_same_speaker:
            turns = self._merge_same_speaker_turns(turns)

        self._check_overlap_and_gaps(turns, transcript.warnings)
        return turns

    # ------------------------------------------------------------------
    # Speaker label cleaning
    # ------------------------------------------------------------------

    def _clean_speaker_labels(
        self,
        turns: List[IntermediateTurn],
        warnings: List[str],
    ) -> List[IntermediateTurn]:
        cleaned: List[IntermediateTurn] = []
        for turn in turns:
            spk = turn.speaker
            if spk is not None:
                spk = _TRAILING_COLON.sub("", spk).strip()
                spk = _EMBEDDED_TIMESTAMP.sub("", spk).strip()
                if not spk or _NULL_SPEAKER_PATTERNS.match(spk):
                    spk = None
            if spk != turn.speaker:
                from dataclasses import replace

                turn = replace(turn, speaker=spk)
            cleaned.append(turn)
        return cleaned

    # ------------------------------------------------------------------
    # End timestamp repair
    # ------------------------------------------------------------------

    def _repair_end_timestamps(
        self,
        turns: List[IntermediateTurn],
        warnings: List[str],
    ) -> List[IntermediateTurn]:
        # Compute estimated duration from turns that have both timestamps
        known_durations = [
            t.end - t.start  # type: ignore[operator]
            for t in turns
            if t.start is not None and t.end is not None and t.end > t.start
        ]
        if known_durations:
            estimated_duration = statistics.median(known_durations)
        else:
            estimated_duration = self.default_estimated_duration

        repaired: List[IntermediateTurn] = []
        for i, turn in enumerate(turns):
            if turn.end is None:
                next_start: Optional[float] = None
                for j in range(i + 1, len(turns)):
                    if turns[j].start is not None:
                        next_start = turns[j].start
                        break

                if next_start is not None and turn.start is not None:
                    new_end = next_start
                else:
                    new_end = (turn.start or 0.0) + estimated_duration

                warnings.append(
                    f"Turn {i}: end timestamp missing; estimated as {new_end:.3f}s"
                )
                # Mark the end as estimated in normalized segment metadata
                from dataclasses import replace

                extra_cue = {"end_estimated": True}
                turn = replace(turn, end=new_end)
                # Carry estimation flag via raw_turn_id annotation is not ideal;
                # the flag will be written into original_cue by SpeakerNormalizer.
                object.__setattr__(turn, "_end_estimated", True)  # transient marker
            repaired.append(turn)
        return repaired

    # ------------------------------------------------------------------
    # Same-speaker merging (disabled by default)
    # ------------------------------------------------------------------

    def _merge_same_speaker_turns(
        self, turns: List[IntermediateTurn]
    ) -> List[IntermediateTurn]:
        if not turns:
            return turns
        merged: List[IntermediateTurn] = [turns[0]]
        for turn in turns[1:]:
            prev = merged[-1]
            same_speaker = prev.speaker == turn.speaker
            no_gap = (
                prev.end is not None
                and turn.start is not None
                and abs(turn.start - prev.end) < 0.001
            )
            if same_speaker and no_gap:
                from dataclasses import replace

                merged[-1] = replace(
                    prev,
                    text=prev.text + " " + turn.text,
                    end=turn.end,
                    words=(
                        (prev.words or []) + (turn.words or [])
                        if prev.words is not None or turn.words is not None
                        else None
                    ),
                )
            else:
                merged.append(turn)
        return merged

    # ------------------------------------------------------------------
    # Overlap/gap checks (warnings only)
    # ------------------------------------------------------------------

    def _check_overlap_and_gaps(
        self,
        turns: List[IntermediateTurn],
        warnings: List[str],
    ) -> None:
        for i, turn in enumerate(turns):
            if turn.start is not None and turn.end is not None:
                if turn.end < turn.start:
                    warnings.append(
                        f"Turn {i}: end ({turn.end:.3f}) < start ({turn.start:.3f})"
                    )

            if i > 0:
                prev = turns[i - 1]
                if (
                    prev.end is not None
                    and turn.start is not None
                    and turn.start - prev.end > self.gap_warning_threshold_s
                ):
                    warnings.append(
                        f"Turn {i}: gap of {turn.start - prev.end:.1f}s before "
                        f"this turn (threshold={self.gap_warning_threshold_s}s)"
                    )

                if (
                    prev.end is not None
                    and turn.start is not None
                    and turn.start < prev.end - 0.01
                ):
                    warnings.append(
                        f"Turn {i}: overlaps with turn {i - 1} "
                        f"(prev_end={prev.end:.3f}, this_start={turn.start:.3f})"
                    )
