"""Tests for web cache helper invalidation."""

from __future__ import annotations

from unittest.mock import MagicMock

import transcriptx.web.cache_helpers as mod


def test_clear_transcript_listing_caches_clears_session_list(monkeypatch) -> None:
    cleared: list[str] = []

    def _track_clear(name: str):
        def _clear() -> None:
            cleared.append(name)

        return _clear

    monkeypatch.setattr(
        mod,
        "cached_list_available_sessions",
        MagicMock(clear=_track_clear("sessions")),
    )
    monkeypatch.setattr(
        mod,
        "cached_list_transcripts",
        MagicMock(clear=_track_clear("transcripts")),
    )
    monkeypatch.setattr(
        mod,
        "cached_get_transcript_summaries_for_paths",
        MagicMock(clear=_track_clear("summaries")),
    )

    mod.clear_transcript_listing_caches()

    assert cleared == ["sessions", "transcripts", "summaries"]
