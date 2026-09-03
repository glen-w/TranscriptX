"""Tests for paths transcripts helpers."""

from pathlib import Path

import pytest

import transcriptx.core.utils.paths as paths_mod


@pytest.fixture
def isolated_paths(tmp_path: Path):
    """Point PATHS transcript roots at tmp so tests never write the user library."""
    transcripts = tmp_path / "transcripts"
    originals = transcripts / "originals"
    metadata = transcripts / "metadata"
    speaker_maps = metadata / "speaker_maps"
    for path in (transcripts, originals, metadata, speaker_maps):
        path.mkdir(parents=True, exist_ok=True)

    previous = {
        "transcripts_dir": paths_mod.PATHS.transcripts_dir,
        "transcripts_originals_dir": paths_mod.PATHS.transcripts_originals_dir,
        "transcripts_metadata_dir": paths_mod.PATHS.transcripts_metadata_dir,
        "transcripts_speaker_maps_dir": paths_mod.PATHS.transcripts_speaker_maps_dir,
    }
    object.__setattr__(paths_mod.PATHS, "transcripts_dir", transcripts)
    object.__setattr__(paths_mod.PATHS, "transcripts_originals_dir", originals)
    object.__setattr__(paths_mod.PATHS, "transcripts_metadata_dir", metadata)
    object.__setattr__(paths_mod.PATHS, "transcripts_speaker_maps_dir", speaker_maps)
    try:
        yield paths_mod.PATHS
    finally:
        for name, value in previous.items():
            object.__setattr__(paths_mod.PATHS, name, value)


def test_canonical_transcript_relpath_accepts_nested_under_transcripts(
    isolated_paths,
) -> None:
    root = isolated_paths.transcripts_dir
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
    isolated_paths, subdir_attr: str
) -> None:
    subdir = getattr(isolated_paths, subdir_attr)
    path = subdir / "foo.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        paths_mod.canonical_transcript_relpath(path)


def test_speaker_map_path_for_transcript_mirrors_relative_structure(
    isolated_paths,
) -> None:
    root = isolated_paths.transcripts_dir
    transcript = root / "clients" / "a" / "call1.json"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text("{}", encoding="utf-8")

    path = paths_mod.speaker_map_path_for_transcript(transcript)
    assert str(path).startswith(str(isolated_paths.transcripts_speaker_maps_dir))
    assert path.name == "call1.speaker_map.json"
    assert "clients/a" in str(path)


def test_speaker_map_path_for_transcript_rejects_originals_and_metadata(
    isolated_paths,
) -> None:
    originals = isolated_paths.transcripts_originals_dir
    meta = isolated_paths.transcripts_metadata_dir

    for base in (originals, meta):
        path = base / "foo.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError):
            paths_mod.speaker_map_path_for_transcript(path)
