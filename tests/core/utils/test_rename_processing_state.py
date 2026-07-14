"""Processing-state rename mutation exact-path and fail-closed validation."""

from __future__ import annotations

from pathlib import Path


from transcriptx.core.utils.rename.names import RenameNames, RenamePaths
from transcriptx.core.utils.rename.processing_state import (
    compute_processing_state_rename_mutation,
    mutate_metadata_for_rename,
)


def test_exact_audio_path_only_rewrites_matching_mp3(tmp_path: Path) -> None:
    """Item 70: same-canonical but different audio file is not rewritten."""
    old_t = tmp_path / "meet.json"
    new_t = tmp_path / "renamed.json"
    old_audio = tmp_path / "meet.mp3"
    other_audio = tmp_path / "meet_en.mp3"
    new_audio = tmp_path / "renamed.mp3"
    names = RenameNames(
        old_stem="meet",
        new_stem="renamed",
        old_canonical="meet",
        new_canonical="renamed",
    )
    paths = RenamePaths.from_transcripts(old_t, new_t)
    meta = {
        "transcript_path": str(old_t),
        "mp3_path": str(other_audio),
        "steps": {"convert": {"mp3_path": str(other_audio)}},
    }
    mutate_metadata_for_rename(
        meta,
        names=names,
        paths=paths,
        planned_old_audio=old_audio,
        planned_new_audio=new_audio,
        rename_timestamp_iso="2020-01-01T00:00:00",
    )
    assert meta["mp3_path"] == str(other_audio)
    assert meta["steps"]["convert"]["mp3_path"] == str(other_audio)


def test_matching_planned_old_audio_is_rewritten(tmp_path: Path) -> None:
    old_t = tmp_path / "meet.json"
    new_t = tmp_path / "renamed.json"
    old_audio = tmp_path / "meet.mp3"
    new_audio = tmp_path / "renamed.mp3"
    names = RenameNames(
        old_stem="meet",
        new_stem="renamed",
        old_canonical="meet",
        new_canonical="renamed",
    )
    paths = RenamePaths.from_transcripts(old_t, new_t)
    meta = {
        "transcript_path": str(old_t),
        "mp3_path": str(old_audio),
        "steps": {"convert": {"mp3_path": str(old_audio)}},
    }
    mutate_metadata_for_rename(
        meta,
        names=names,
        paths=paths,
        planned_old_audio=old_audio,
        planned_new_audio=new_audio,
        rename_timestamp_iso="2020-01-01T00:00:00",
    )
    assert meta["mp3_path"] == str(new_audio)
    assert meta["steps"]["convert"]["mp3_path"] == str(new_audio)


def test_schema_invalid_state_entry_blocks_mutation(tmp_path: Path) -> None:
    """Item 69: invalid proposed document surfaces validation msgs."""
    old_t = tmp_path / "a.json"
    new_t = tmp_path / "b.json"
    old_t.write_text("{}")
    names = RenameNames.from_paths(old_t, new_t)
    paths = RenamePaths.from_transcripts(old_t, new_t)
    state = {
        "processed_files": {
            "k1": {
                # missing required processed_at/status
                "transcript_path": str(old_t),
            }
        }
    }
    mutation = compute_processing_state_rename_mutation(
        state,
        names=names,
        paths=paths,
        planned_old_audio=None,
        planned_new_audio=None,
        rename_timestamp_iso="2020-01-01T00:00:00",
    )
    assert mutation is not None
    assert mutation.sibling_path_validation_msgs
