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
