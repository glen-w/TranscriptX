"""Web-layer consumption of speaker profile CacheInvalidationSignal.

Core must not import Streamlit; this module is the only place that clears
``@st.cache_data`` helpers from profile-store signals.
"""

from __future__ import annotations

from transcriptx.core.speaker_profiles.signals import CacheInvalidationSignal


def consume_cache_invalidation_signal(signal: CacheInvalidationSignal | None) -> None:
    """Map signal scopes to Streamlit cache clears."""
    if signal is None:
        return

    scopes = set(signal.scopes)
    if scopes & {"transcript_summaries", "speaker_profiles", "speaker_links"}:
        from transcriptx.web.cache_helpers import clear_transcript_listing_caches

        clear_transcript_listing_caches()

    if "speaker_profiles" in scopes or "speaker_links" in scopes:
        try:
            from transcriptx.web.page_modules.speaker_id import (
                _transcript_paths_for_speaker_views,
            )

            _transcript_paths_for_speaker_views.clear()  # type: ignore[attr-defined]
        except Exception:
            pass
