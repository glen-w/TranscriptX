"""Tests for search service path resolution."""

from __future__ import annotations

from pathlib import Path


def test_resolve_session_path_for_search_falls_back_when_missing(monkeypatch) -> None:
    import transcriptx.web.services.search_service as mod

    monkeypatch.setattr(
        mod.FileService,
        "resolve_transcript_path",
        lambda _session_name: None,
    )

    assert mod._resolve_session_path_for_search("slug/run-1") == "slug/run-1"


def test_resolve_session_path_for_search_uses_flat_transcript_path(monkeypatch) -> None:
    import transcriptx.web.services.search_service as mod

    monkeypatch.setattr(
        mod.FileService,
        "resolve_transcript_path",
        lambda _session_name: Path("/data/slug.json"),
    )

    assert mod._resolve_session_path_for_search("slug") == "/data/slug.json"


def test_resolve_session_path_for_search_uses_run_linked_transcript_path(
    monkeypatch,
) -> None:
    import transcriptx.web.services.search_service as mod

    monkeypatch.setattr(
        mod.FileService,
        "resolve_transcript_path",
        lambda _session_name: Path("/outputs/slug/run1/transcript.json"),
    )

    assert (
        mod._resolve_session_path_for_search("slug/run1")
        == "/outputs/slug/run1/transcript.json"
    )
