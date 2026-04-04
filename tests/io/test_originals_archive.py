"""Tests for originals archive path disambiguation."""

from __future__ import annotations

from pathlib import Path

from transcriptx.io.originals_archive import disambiguate_originals_archive_path


def test_returns_free_path_when_missing(tmp_path: Path) -> None:
    originals = tmp_path / "originals"
    p = disambiguate_originals_archive_path("meet.srt", originals)
    assert p == originals / "meet.srt"


def test_reuses_path_when_staging_is_same_file(tmp_path: Path) -> None:
    originals = tmp_path / "originals"
    originals.mkdir()
    staging = originals / "meet.srt"
    staging.write_text("x", encoding="utf-8")
    p = disambiguate_originals_archive_path(
        "meet.srt", originals, staging_path=staging
    )
    assert p == staging


def test_numeric_suffix_only_on_real_collision(tmp_path: Path) -> None:
    originals = tmp_path / "originals"
    originals.mkdir()
    (originals / "meet.srt").write_text("old", encoding="utf-8")
    staging = tmp_path / "staging" / "meet.srt"
    staging.parent.mkdir()
    staging.write_text("new", encoding="utf-8")
    p = disambiguate_originals_archive_path(
        "meet.srt", originals, staging_path=staging
    )
    assert p == originals / "meet (1).srt"
