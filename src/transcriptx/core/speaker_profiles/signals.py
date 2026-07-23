"""Cache invalidation signal returned by SpeakerProfileService mutations.

Core must not import Streamlit. The web layer maps scopes to @st.cache_data clears.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CacheScope = Literal[
    "speaker_profiles",
    "speaker_links",
    "transcript_summaries",
    "speaker_voice",
]


@dataclass(frozen=True)
class CacheInvalidationSignal:
    """Frozen signal describing which web caches should be cleared."""

    scopes: tuple[CacheScope, ...]
    profile_ids: tuple[str, ...] = field(default_factory=tuple)
    link_ids: tuple[str, ...] = field(default_factory=tuple)
    managed_transcript_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.scopes:
            raise ValueError("CacheInvalidationSignal requires at least one scope")
