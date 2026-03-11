"""
Speaker normalization for transcript imports.

Accepts ``List[IntermediateTurn]`` (the only input type — the legacy
``CueWithSpeaker = Union[VTTCue, SRTCue]`` union has been removed).
``VTTAdapter`` and ``SRTAdapter`` each convert their cue objects into
``IntermediateTurn`` before calling this module.

Maps raw speaker labels to standardised ``SPEAKER_XX`` format or ``None``
when no speaker information is present.  Preserves original labels in
``original_cue.original_speaker`` for downstream use.

Returns ``List[TranscriptSegment]`` — a TypedDict capturing the schema v1.0
segment shape (``start``, ``end``, ``speaker``, ``text``, optional fields).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.intermediate_transcript import IntermediateTurn, TranscriptSegment

logger = get_logger()


def assign_speaker_ids(unique_speakers: List[str]) -> Dict[str, str]:
    """Map sorted unique speaker labels to ``SPEAKER_XX`` identifiers.

    Args:
        unique_speakers: Unique, non-None speaker label strings.

    Returns:
        ``{original_label: "SPEAKER_XX"}`` mapping.
    """
    return {
        spk: f"SPEAKER_{idx:02d}" for idx, spk in enumerate(sorted(unique_speakers))
    }


def normalize_speakers(turns: List[IntermediateTurn]) -> List[TranscriptSegment]:
    """Normalise raw speaker labels from a list of IntermediateTurn objects.

    Rules:
    - If no turn has a speaker label: ``speaker`` is ``null`` in all segments
      (no fake diarisation).
    - If any speaker labels are present: map to ``SPEAKER_XX`` format.
    - Original labels are preserved in ``original_cue.original_speaker``.

    Args:
        turns: List of IntermediateTurn objects (output of TranscriptNormalizer).

    Returns:
        List of TranscriptSegment dicts conforming to schema v1.0.
    """
    # Collect unique non-None speaker labels
    unique_speakers = list(
        dict.fromkeys(t.speaker for t in turns if t.speaker is not None)
    )
    has_speakers = bool(unique_speakers)

    if not has_speakers:
        logger.info(
            "No speaker labels found — setting speaker to null for all segments"
        )
        speaker_mapping: Dict[str, str] = {}
    else:
        speaker_mapping = assign_speaker_ids(unique_speakers)
        logger.info(f"Found {len(speaker_mapping)} unique speaker(s)")
        for original, normalised in speaker_mapping.items():
            logger.debug(f"  {original!r} -> {normalised!r}")

    segments: List[TranscriptSegment] = []
    for turn in turns:
        raw_speaker = turn.speaker
        normalised_speaker: Optional[str] = (
            speaker_mapping.get(raw_speaker) if raw_speaker is not None else None
        )

        seg: TranscriptSegment = {
            "start": turn.start if turn.start is not None else 0.0,
            "end": turn.end if turn.end is not None else 0.0,
            "speaker": normalised_speaker,
            "text": turn.text,
        }

        if turn.raw_turn_id is not None:
            seg["cue_id"] = turn.raw_turn_id

        if turn.words is not None:
            seg["words"] = turn.words

        # Build original_cue metadata
        original_cue: Dict[str, Any] = {}

        if raw_speaker is not None:
            original_cue["original_speaker"] = raw_speaker

        # Carry end-estimation flag from TranscriptNormalizer if present
        if getattr(turn, "_end_estimated", False):
            original_cue["end_estimated"] = True

        if original_cue:
            seg["original_cue"] = original_cue

        segments.append(seg)

    return segments
