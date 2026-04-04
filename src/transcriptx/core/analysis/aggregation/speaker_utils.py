"""
Helpers for resolving canonical speaker display names in group aggregation.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from transcriptx.core.pipeline.speaker_normalizer import (  # type: ignore[import]
    CanonicalSpeakerMap,
)
from transcriptx.core.utils.speaker_extraction import (  # type: ignore[import]
    extract_speaker_info,
)
from transcriptx.utils.text_utils import is_eligible_named_speaker  # type: ignore[import]


def resolve_canonical_speaker(
    segment: Dict[str, Any],
    transcript_path: str,
    canonical_speaker_map: CanonicalSpeakerMap,
    ignored_ids: set[str] | None = None,
) -> Optional[Tuple[int, str]]:
    """
    Return (canonical_id, display_name) for a segment or None when unidentified.

    Uses the same local key that speaker_normalizer stored in
    CanonicalSpeakerMap.transcript_to_speakers.
    """
    info = extract_speaker_info(segment)
    if info is None:
        return None

    display_name = info.display_name or str(info.grouping_key)
    if not is_eligible_named_speaker(
        display_name, str(info.grouping_key), ignored_ids or set()
    ):
        return None

    local_to_canonical = canonical_speaker_map.transcript_to_speakers.get(
        transcript_path, {}
    )
    canonical_id = local_to_canonical.get(str(info.grouping_key))
    if canonical_id is None:
        return None

    canonical_display = canonical_speaker_map.canonical_to_display.get(
        canonical_id, display_name
    )
    return canonical_id, str(canonical_display)
