"""Tests for paths transcripts helpers."""

from pathlib import Path

import pytest

import transcriptx.core.utils.paths as paths_mod


def test_canonical_transcript_relpath_accepts_nested_under_transcripts(
    tmp_path: Path,
) -> None:
    root = paths_mod.PATHS.transcripts_dir
    nested = root / "projects" / "foo" / "call1.json"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("{}", encoding="utf-8")

    rel = paths_mod.canonical_transcript_relpath(nested)
    assert rel == Path("projects/foo/call1.json")


@pytest.mark.parametrize(
    "subdir_attr",
    ["transcripts_originals_dir", "transcripts_metadata_dir"],
)
def test_canonical_transcript_relpath_rejects_originals_and_metadata(
    subdir_attr: str,
) -> None:
    subdir = getattr(paths_mod.PATHS, subdir_attr)
    path = subdir / "foo.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        paths_mod.canonical_transcript_relpath(path)


def test_speaker_map_path_for_transcript_mirrors_relative_structure(
    tmp_path: Path,
) -> None:
    root = paths_mod.PATHS.transcripts_dir
    transcript = root / "clients" / "a" / "call1.json"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text("{}", encoding="utf-8")

    path = paths_mod.speaker_map_path_for_transcript(transcript)
    assert str(path).startswith(str(paths_mod.PATHS.transcripts_speaker_maps_dir))
    assert path.name == "call1.speaker_map.json"
    assert "clients/a" in str(path)


def test_speaker_map_path_for_transcript_rejects_originals_and_metadata(
    tmp_path: Path,
) -> None:
    originals = paths_mod.PATHS.transcripts_originals_dir
    meta = paths_mod.PATHS.transcripts_metadata_dir

    for base in (originals, meta):
        path = base / "foo.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError):
            paths_mod.speaker_map_path_for_transcript(path)
