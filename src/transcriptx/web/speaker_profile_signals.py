"""Web-layer consumption of speaker profile CacheInvalidationSignal.

Core must not import Streamlit; this module is the only place that clears
``@st.cache_data`` helpers from profile-store signals.
"""

from __future__ import annotations

from transcriptx.core.speaker_profiles.signals import CacheInvalidationSignal

# Session keys shared by Settings → Speakers and the Speakers page.
INCLUDE_IGNORED_SESSION_KEY = "speakers_include_ignored"
SHOW_ARCHIVED_SESSION_KEY = "speakers_show_archived"
SHOW_MERGED_SESSION_KEY = "speakers_show_merged"


def consume_cache_invalidation_signal(signal: CacheInvalidationSignal | None) -> None:
    """Map signal scopes to Streamlit cache clears."""
    if signal is None:
        return

    scopes = set(signal.scopes)
    if scopes & {
        "transcript_summaries",
        "speaker_profiles",
        "speaker_links",
        "speaker_voice",
    }:
        from transcriptx.web.cache_helpers import clear_transcript_listing_caches

        clear_transcript_listing_caches()

    if "speaker_profiles" in scopes or "speaker_links" in scopes or "speaker_voice" in scopes:
        try:
            from transcriptx.web.page_modules.speaker_id import (
                _transcript_paths_for_speaker_views,
            )

            _transcript_paths_for_speaker_views.clear()  # type: ignore[attr-defined]
        except Exception:
            pass
