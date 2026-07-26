"""Tests for sidebar options."""

from __future__ import annotations

from pathlib import Path

import transcriptx.web.sidebar_options as mod


def test_build_session_index_from_list() -> None:
    out = mod._build_session_index_from_list(
        [{"name": "slug/run1"}, {"name": "invalid"}]
    )
    assert "slug" in out
    assert out["slug"][0]["run_id"] == "run1"


def test_session_list_covers_transcript_path(monkeypatch, tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        mod.FileService,
        "resolve_transcript_path",
        lambda _name: transcript,
    )
    assert mod._session_list_covers_transcript_path([{"name": "s/r"}], transcript)


def test_slug_display_labels_from_index(monkeypatch) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.load_index",
        lambda: {"transcripts": {"k": {"slug": "slug1", "source_basename": "file"}}},
    )
    labels = mod._slug_display_labels_from_index()
    assert labels["slug1"] == "file"


def test_cached_dropdown_options_prefers_registered_slug_for_library_only(
    monkeypatch, tmp_path: Path
) -> None:
    """Imports with no runs must list slug (not only path) so nav subject survives."""
    transcript = tmp_path / "R20241025-162403.json"
    transcript.write_text("{}", encoding="utf-8")
    resolved = str(transcript.resolve())

    monkeypatch.setattr(
        mod,
        "_slug_display_labels_from_index",
        lambda: {"R20241025-162403": "R20241025-162403"},
    )
    monkeypatch.setattr(
        mod,
        "_resolved_source_path_to_slug_from_index",
        lambda: {resolved: "R20241025-162403"},
    )
    monkeypatch.setattr(mod, "_cached_session_path_index", lambda _names: (set(), set()))

    options, _labels = mod._cached_dropdown_options.__wrapped__(
        (),
        (resolved,),
        None,
    )
    assert "R20241025-162403" in options
    assert resolved not in options
