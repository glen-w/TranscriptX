"""path_resolution_core pure helpers and filesystem-backed resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.utils import paths as paths_module
from transcriptx.core.utils.path_resolution_core import (
    find_state_entry_by_path,
    get_path_from_state,
    heuristic_search,
    try_canonical_base_match,
    try_suffix_variants,
    validate_resolved_file_type,
)


@pytest.fixture
def patched_paths(monkeypatch, tmp_path):
    """Isolate the module-level path constants under tmp dirs."""
    diarised = tmp_path / "diarised"
    outputs = tmp_path / "outputs"
    recordings = tmp_path / "recordings"
    state_file = tmp_path / "processing_state.json"
    diarised.mkdir()
    outputs.mkdir()
    recordings.mkdir()
    monkeypatch.setattr(paths_module, "DIARISED_TRANSCRIPTS_DIR", diarised)
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(paths_module, "RECORDINGS_DIR", recordings)
    monkeypatch.setattr(paths_module, "PROCESSING_STATE_FILE", state_file)
    return {
        "diarised": diarised,
        "outputs": outputs,
        "recordings": recordings,
        "state_file": state_file,
    }


@pytest.mark.unit
def test_validate_resolved_file_type_audio_and_transcript() -> None:
    assert validate_resolved_file_type(Path("a.mp3"), "audio") is True
    assert validate_resolved_file_type(Path("a.json"), "transcript") is True
    assert validate_resolved_file_type(Path("a.txt"), "transcript") is False


@pytest.mark.unit
def test_validate_resolved_file_type_output_dir(tmp_path: Path) -> None:
    d = tmp_path / "out"
    d.mkdir()
    assert validate_resolved_file_type(d, "output_dir") is True
    assert validate_resolved_file_type(tmp_path / "nope.txt", "output_dir") is False


@pytest.mark.unit
def test_validate_resolved_file_type_unknown_type_defaults_true() -> None:
    assert validate_resolved_file_type(Path("anything.xyz"), "other") is True


@pytest.mark.unit
def test_find_state_entry_by_path_direct_transcript_path() -> None:
    processed = {
        "k1": {"transcript_path": "/data/t.json"},
    }
    hit = find_state_entry_by_path("/data/t.json", processed)
    assert hit is not None
    assert hit[0] == "k1"


@pytest.mark.unit
def test_find_state_entry_by_canonical_base_name() -> None:
    processed = {
        "k1": {"canonical_base_name": "meeting_notes", "transcript_path": ""},
    }
    hit = find_state_entry_by_path("/vol/meeting_notes.json", processed)
    assert hit is not None
    assert hit[0] == "k1"


@pytest.mark.unit
def test_find_state_entry_by_step_transcript_path() -> None:
    processed = {
        "k1": {
            "transcript_path": "",
            "steps": {"transcribe": {"transcript_path": "/data/t.json"}},
        },
    }
    hit = find_state_entry_by_path("/data/t.json", processed)
    assert hit is not None
    assert hit[0] == "k1"


@pytest.mark.unit
def test_find_state_entry_by_variant_base_same_stem_other_dir() -> None:
    processed = {
        "k1": {"transcript_path": "/archive/2024/meeting.json"},
    }
    hit = find_state_entry_by_path("/inbox/meeting.json", processed)
    assert hit is not None
    assert hit[0] == "k1"


@pytest.mark.unit
def test_find_state_entry_no_match_returns_none() -> None:
    processed = {"k1": {"transcript_path": "/x/alpha.json"}}
    assert find_state_entry_by_path("/y/beta.json", processed) is None


@pytest.mark.unit
def test_get_path_from_state_missing_file_returns_none(patched_paths) -> None:
    # State file does not exist -> None
    assert get_path_from_state("/any/file.json", "transcript") is None


@pytest.mark.unit
def test_get_path_from_state_transcript_existing(patched_paths, tmp_path) -> None:
    transcript = tmp_path / "real.json"
    transcript.write_text("{}", encoding="utf-8")
    tpath = str(transcript)
    state = {"processed_files": {"k1": {"transcript_path": tpath}}}
    patched_paths["state_file"].write_text(json.dumps(state), encoding="utf-8")

    result = get_path_from_state(tpath, "transcript", validate=False)
    assert result == tpath


@pytest.mark.unit
def test_get_path_from_state_audio_and_output_dir(patched_paths, tmp_path) -> None:
    transcript = tmp_path / "real.json"
    transcript.write_text("{}", encoding="utf-8")
    tpath = str(transcript)
    state = {
        "processed_files": {
            "k1": {
                "transcript_path": tpath,
                "mp3_path": "/audio/real.mp3",
                "output_dir_path": "/outputs/real",
            }
        }
    }
    patched_paths["state_file"].write_text(json.dumps(state), encoding="utf-8")

    assert get_path_from_state(tpath, "audio", validate=False) == "/audio/real.mp3"
    assert get_path_from_state(tpath, "output_dir", validate=False) == "/outputs/real"


@pytest.mark.unit
def test_try_canonical_base_match_transcript_in_diarised(patched_paths) -> None:
    target = patched_paths["diarised"] / "meeting.json"
    target.write_text("{}", encoding="utf-8")
    result = try_canonical_base_match("meeting", "transcript")
    assert result is not None
    assert Path(result) == target.resolve()


@pytest.mark.unit
def test_try_canonical_base_match_audio_in_recordings(patched_paths) -> None:
    target = patched_paths["recordings"] / "talk.mp3"
    target.write_text("x", encoding="utf-8")
    result = try_canonical_base_match("talk", "audio")
    assert result is not None
    assert Path(result) == target.resolve()


@pytest.mark.unit
def test_try_canonical_base_match_output_dir(patched_paths) -> None:
    out = patched_paths["outputs"] / "session1"
    out.mkdir()
    result = try_canonical_base_match("session1", "output_dir")
    assert result is not None
    assert Path(result) == out.resolve()


@pytest.mark.unit
def test_try_canonical_base_match_not_found_returns_none(patched_paths) -> None:
    assert try_canonical_base_match("missing", "transcript") is None


@pytest.mark.unit
def test_try_suffix_variants_equal_base_returns_none(patched_paths) -> None:
    assert try_suffix_variants("same", "same", "transcript") is None


@pytest.mark.unit
def test_try_suffix_variants_delegates_for_differing_base(patched_paths) -> None:
    target = patched_paths["diarised"] / "alias.json"
    target.write_text("{}", encoding="utf-8")
    result = try_suffix_variants("alias", "canonical", "transcript")
    assert result is not None
    assert Path(result) == target.resolve()


@pytest.mark.unit
def test_heuristic_search_finds_transcript_in_outputs(patched_paths) -> None:
    found = patched_paths["outputs"] / "report.json"
    found.write_text("{}", encoding="utf-8")
    result = heuristic_search(
        "/somewhere/report.json", "transcript", base_name="report"
    )
    assert result is not None
    assert Path(result) == found.resolve()


@pytest.mark.unit
def test_heuristic_search_no_match_returns_none(patched_paths) -> None:
    assert heuristic_search("/nope/ghost.json", "transcript", base_name="ghost") is None
