"""Tests for transcriptx library-paths (Nightshift helper)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from transcriptx.library_paths import main


def test_library_paths_recent_and_missing_modules(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text("{}", encoding="utf-8")
    b.write_text("{}", encoding="utf-8")
    a.touch()
    b.touch()

    def fake_discover():
        return [str(a), str(b)]

    def fake_targets(*, modules, force=False):
        return [(a, ["transcript_output", "llm_summary"])]

    with (
        patch(
            "transcriptx.core.utils.file_discovery.discover_managed_transcript_paths",
            fake_discover,
        ),
        patch("transcriptx.analyze_modules._discover_targets", fake_targets),
        patch("transcriptx.analyze_modules._parse_modules", lambda raw: raw.split(",")),
        patch("transcriptx._bootstrap.bootstrap", lambda: None),
    ):
        import io
        import sys

        buf = io.StringIO()
        with patch.object(sys, "stdout", buf):
            rc = main(["--recent", "2", "--missing-modules", "llm_summary"])
        assert rc == 0
        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        assert lines == [str(a)]
