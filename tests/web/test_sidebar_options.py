"""Tests for sidebar options."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import transcriptx.web.sidebar_options as mod


def test_build_session_index_from_list() -> None:
    out = mod._build_session_index_from_list(
        [{"name": "slug/run1"}, {"name": "invalid"}]
    )
    assert "slug" in out
    assert out["slug"][0]["run_id"] == "run1"


def test_slug_display_labels_from_index(monkeypatch) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.load_index",
        lambda: {"transcripts": {"k": {"slug": "slug1", "source_basename": "file"}}},
    )
    labels = mod._slug_display_labels_from_index()
    assert labels["slug1"] == "file"


def test_cached_dropdown_options_includes_library_only_slug(monkeypatch) -> None:
    """Imports with no runs must list slug so nav subject survives hydration."""
    monkeypatch.setattr(
        mod,
        "_slug_display_labels_from_index",
        lambda: {"R20241025-162403": "R20241025-162403"},
    )
    monkeypatch.setattr(
        mod,
        "_library_only_slugs_from_index",
        lambda _session_slugs: ["R20241025-162403"],
    )

    options, _labels = mod._cached_dropdown_options.__wrapped__(
        (),
        None,
    )
    assert "R20241025-162403" in options


def test_library_only_slugs_skips_missing_source_path(
    monkeypatch, tmp_path: Path
) -> None:
    present = tmp_path / "ok.json"
    present.write_text("{}", encoding="utf-8")
    missing = tmp_path / "gone.json"

    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.list_all_transcripts",
        lambda: [
            {
                "slug": "present-slug",
                "source_path": str(present),
                "source_basename": "ok",
            },
            {
                "slug": "missing-slug",
                "source_path": str(missing),
                "source_basename": "gone",
            },
            {"slug": "already-run", "source_path": str(present)},
        ],
    )
    extras = mod._library_only_slugs_from_index({"already-run"})
    assert extras == ["present-slug"]


def test_get_transcript_dropdown_options_uses_light_listing(monkeypatch) -> None:
    """Dropdown must not pull rich sessions or full library metadata."""
    rich = MagicMock(side_effect=AssertionError("rich sessions should not be used"))
    library = MagicMock(
        side_effect=AssertionError("library metadata should not be used")
    )
    monkeypatch.setattr(mod, "cached_list_available_sessions", rich)
    monkeypatch.setattr(
        "transcriptx.web.cache_helpers.get_cached_list_transcripts",
        library,
        raising=False,
    )
    monkeypatch.setattr(
        mod,
        "cached_list_viewable_session_names",
        lambda: ["slug-a/run1"],
    )
    monkeypatch.setattr(mod, "_slug_index_mtime", lambda: 1.0)
    monkeypatch.setattr(
        mod,
        "_cached_dropdown_options",
        lambda _names, _mtime: (["slug-a", "import-only"], {"slug-a": "A"}),
    )

    options, formatter = mod.get_transcript_dropdown_options()
    assert options == ["slug-a", "import-only"]
    assert formatter("slug-a") == "A"
    rich.assert_not_called()
    library.assert_not_called()
