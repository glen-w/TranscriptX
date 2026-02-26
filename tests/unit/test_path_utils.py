from __future__ import annotations

import os
from pathlib import Path

import pytest

from transcriptx.core.utils import _path_core


def test_get_canonical_base_name_strips_suffixes() -> None:
    assert (
        _path_core.get_canonical_base_name("/tmp/meeting_transcript.json") == "meeting"
    )
    assert (
        _path_core.get_canonical_base_name("/tmp/session_transcript_diarised.json")
        == "session"
    )
    assert _path_core.get_canonical_base_name("/tmp/demo_diarised.json") == "demo"


def test_get_transcript_dir_uses_override(tmp_path: Path) -> None:
    transcript_path = str(tmp_path / "sample.json")
    override_dir = str(tmp_path / "override")
    _path_core.set_transcript_output_dir(transcript_path, override_dir)
    try:
        assert _path_core.get_transcript_dir(transcript_path) == override_dir
    finally:
        _path_core.clear_transcript_output_dir(transcript_path)


def test_get_enriched_transcript_path_uses_standard_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_path_core, "OUTPUTS_DIR", str(tmp_path))
    transcript_path = os.path.join(str(tmp_path), "meeting.json")
    expected = os.path.join(
        str(tmp_path),
        "meeting",
        "sentiment",
        "data",
        "global",
        "meeting_with_sentiment.json",
    )
    assert (
        _path_core.get_enriched_transcript_path(transcript_path, "sentiment")
        == expected
    )
