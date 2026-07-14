"""Contract and regression tests for file_rename (atomicity, dry-run, precedence)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.utils import file_rename as fr
from transcriptx.core.utils._path_core import get_transcript_dir


def _managed_old_name_transcript_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict:
    """Managed ``old_name.json`` + import sidecar + ``outputs/old_name`` + processing state."""
    from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
    from transcriptx.io.transcript_schema import (
        SourceInfo,
        TranscriptMetadata,
        create_transcript_document,
    )

    root = tmp_path / "lib"
    transcripts = root / "transcripts"
    metadata_dir = root / "metadata"
    originals = root / "originals"
    for d in (transcripts, metadata_dir, originals):
        d.mkdir(parents=True)
    (originals / "f.srt").write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata_dir
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR", transcripts
    )

    transcript = transcripts / "old_name.json"
    doc = create_transcript_document(
        [{"speaker": "SPEAKER_00", "text": "Hi", "start": 0.0, "end": 1.0}],
        SourceInfo(
            type="srt",
            original_path="originals/f.srt",
            imported_at="2026-01-01T00:00:00+00:00",
            file_hash="h",
            file_mtime=0.0,
        ),
        TranscriptMetadata(duration_seconds=1.0, segment_count=1, speaker_count=1),
    )
    transcript.write_text(json.dumps(doc), encoding="utf-8")
    write_initial_sidecar(
        transcript,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="f.srt",
        archived_original_relpath="originals/f.srt",
    )

    outputs = tmp_path / "outputs"
    recordings = tmp_path / "recordings"
    state_dir = tmp_path / "state"
    outputs.mkdir(parents=True)
    recordings.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    (outputs / "old_name").mkdir()
    (outputs / "old_name" / "marker.txt").write_text("x")

    state_file = state_dir / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "u1": {
                        "transcript_path": str(transcript),
                        "processed_at": "2020-01-01T00:00:00",
                        "status": "completed",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("transcriptx.core.utils.paths.OUTPUTS_DIR", outputs)
    monkeypatch.setattr("transcriptx.core.utils._path_core.OUTPUTS_DIR", outputs)
    monkeypatch.setattr(fr, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(fr, "RECORDINGS_DIR", recordings)
    monkeypatch.setattr(fr, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE", state_file
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.pipeline.PROCESSING_STATE_FILE", state_file
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.audio_association.PROCESSING_STATE_FILE",
        state_file,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.audio_association.RECORDINGS_DIR", recordings
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.audio_association.OUTPUTS_DIR", outputs
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.processing_state.PROCESSING_STATE_FILE",
        state_file,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.processing_state.OUTPUTS_DIR", outputs
    )
    monkeypatch.setattr("transcriptx.core.utils.rename.journal.STATE_DIR", state_dir)

    return {
        "transcript": transcript,
        "outputs": outputs,
        "recordings": recordings,
        "state_file": state_file,
        "state_dir": state_dir,
        "metadata_dir": metadata_dir,
        "transcripts": transcripts,
    }


def test_find_original_audio_uuid_missing_audio_path_prefers_mp3_over_convert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UUID entry: no audio_path; mp3_path wins over nested convert paths when all exist."""
    transcript = tmp_path / "meeting.json"
    transcript.write_text("{}", encoding="utf-8")
    transcript_path = str(transcript)

    mp3 = tmp_path / "from_mp3.mp3"
    top = tmp_path / "from_top.mp3"
    nested = tmp_path / "from_nested.mp3"
    for p in (mp3, top, nested):
        p.write_bytes(b"x")

    state_file = tmp_path / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "f5e5bd96-aef4-4b4a-ad44-5c96aa120337": {
                        "transcript_path": transcript_path,
                        "mp3_path": str(mp3),
                        "convert": {"mp3_path": str(top)},
                        "steps": {"convert": {"mp3_path": str(nested)}},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(fr, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(fr, "RECORDINGS_DIR", tmp_path / "empty_rec")
    monkeypatch.setattr(fr, "OUTPUTS_DIR", tmp_path / "outputs")
    (tmp_path / "empty_rec").mkdir()

    assert fr.find_original_audio_file(transcript_path) == mp3


def test_find_original_audio_top_level_convert_before_nested_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When mp3_path missing, top-level convert.mp3_path wins over steps.convert.mp3_path."""
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    transcript_path = str(transcript)

    top = tmp_path / "top.wav"
    nested = tmp_path / "nested.wav"
    top.write_bytes(b"a")
    nested.write_bytes(b"b")

    state_file = tmp_path / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "uuid-here-0000-0000-0000-000000000001": {
                        "transcript_path": transcript_path,
                        "convert": {"mp3_path": str(top)},
                        "steps": {"convert": {"mp3_path": str(nested)}},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(fr, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(fr, "RECORDINGS_DIR", tmp_path / "rec")
    monkeypatch.setattr(fr, "OUTPUTS_DIR", tmp_path / "outputs")
    (tmp_path / "rec").mkdir()

    assert fr.find_original_audio_file(transcript_path) == top


def test_find_original_audio_multiple_hits_exact_precedence_state_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """audio_path beats mp3_path when both exist (first in policy order wins)."""
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    a1 = tmp_path / "a.wav"
    a2 = tmp_path / "b.mp3"
    a1.write_bytes(b"1")
    a2.write_bytes(b"2")

    state_file = tmp_path / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "uuid-00000000-0000-0000-0000-000000000099": {
                        "transcript_path": str(transcript),
                        "audio_path": str(a1),
                        "mp3_path": str(a2),
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(fr, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(fr, "RECORDINGS_DIR", tmp_path / "rec")
    monkeypatch.setattr(fr, "OUTPUTS_DIR", tmp_path / "outputs")
    (tmp_path / "rec").mkdir()

    assert fr.find_original_audio_file(str(transcript)) == a1


def test_update_processing_state_matches_resolved_transcript_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Entry matched via resolved path (different string form) still updates."""
    from transcriptx.core.utils.processing_state import save_processing_state

    old_tp = tmp_path / "sub" / "x.json"
    old_tp.parent.mkdir(parents=True)
    old_tp.write_text("{}", encoding="utf-8")
    new_tp = tmp_path / "sub" / "y.json"

    state = {
        "processed_files": {
            "k": {
                "transcript_path": str(old_tp.resolve()),
                "mp3_path": str(tmp_path / "a.mp3"),
                "output_dir_path": str(tmp_path / "out_old"),
                "canonical_base_name": "x",
            }
        }
    }
    state_file = tmp_path / "processing_state.json"
    save_processing_state(state, state_file)

    monkeypatch.setattr(fr, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE", state_file
    )
    monkeypatch.setattr(fr, "OUTPUTS_DIR", tmp_path / "outputs")
    (tmp_path / "outputs").mkdir(parents=True)

    # Use unresolved path for old_path if it still resolves equal to stored path
    fr.update_processing_state(str(old_tp), str(new_tp), "x", "y")

    loaded = json.loads(state_file.read_text(encoding="utf-8"))
    entry = loaded["processed_files"]["k"]
    assert entry["transcript_path"] == str(new_tp)
    assert entry["current_transcript_path"] == str(new_tp)


def test_rename_transcript_blocks_when_working_audio_target_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If renameable working-copy audio target already exists, block the whole rename."""
    env = _managed_old_name_transcript_env(tmp_path, monkeypatch)
    transcript = env["transcript"]
    recordings = env["recordings"]
    state_file = env["state_file"]

    old_audio = recordings / "old_name.mp3"
    new_audio = recordings / "new_name.mp3"
    old_audio.write_bytes(b"old")
    new_audio.write_bytes(b"pre")
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "u1": {
                        "transcript_path": str(transcript),
                        "mp3_path": str(old_audio),
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    outcome = fr.rename_transcript_files_with_outcome(
        "old_name", "new_name", str(transcript)
    )
    assert outcome.ok is False
    assert outcome.transaction_committed is False
    assert transcript.exists()
    assert old_audio.exists()
    assert new_audio.read_bytes() == b"pre"


def test_rename_finalize_failure_returns_false_without_transaction_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finalize failure: transaction stays committed; do not rollback after partial finalize."""
    from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
    from transcriptx.io.transcript_schema import (
        SourceInfo,
        TranscriptMetadata,
        create_transcript_document,
    )

    root = tmp_path / "lib"
    transcripts = root / "transcripts"
    metadata_dir = root / "metadata"
    originals = root / "originals"
    for d in (transcripts, metadata_dir, originals):
        d.mkdir(parents=True)
    (originals / "f.srt").write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata_dir
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR", transcripts
    )

    transcript = transcripts / "old_name.json"
    doc = create_transcript_document(
        [{"speaker": "SPEAKER_00", "text": "Hi", "start": 0.0, "end": 1.0}],
        SourceInfo(
            type="srt",
            original_path="originals/f.srt",
            imported_at="2026-01-01T00:00:00+00:00",
            file_hash="h",
            file_mtime=0.0,
        ),
        TranscriptMetadata(duration_seconds=1.0, segment_count=1, speaker_count=1),
    )
    transcript.write_text(json.dumps(doc), encoding="utf-8")
    write_initial_sidecar(
        transcript,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="f.srt",
        archived_original_relpath="originals/f.srt",
    )

    outputs = tmp_path / "outputs"
    recordings = tmp_path / "recordings"
    outputs.mkdir(parents=True)
    recordings.mkdir(parents=True)
    out_old = outputs / "old_name"
    out_old.mkdir()
    (out_old / "artifact.txt").write_text("data", encoding="utf-8")

    state_file = tmp_path / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "u1": {
                        "transcript_path": str(transcript),
                        "mp3_path": "",
                        "processed_at": "2020-01-01T00:00:00",
                        "status": "completed",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("transcriptx.core.utils.paths.OUTPUTS_DIR", outputs)
    monkeypatch.setattr("transcriptx.core.utils._path_core.OUTPUTS_DIR", outputs)
    monkeypatch.setattr(fr, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(fr, "RECORDINGS_DIR", recordings)
    monkeypatch.setattr(fr, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE", state_file
    )

    monkeypatch.setattr(fr, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.pipeline.PROCESSING_STATE_FILE", state_file
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.journal.STATE_DIR", tmp_path / "state"
    )
    (tmp_path / "state").mkdir(exist_ok=True)
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.pipeline.finalize_output_directory_move",
        lambda *a, **k: (_ for _ in ()).throw(
            OSError("simulated finalize move failure")
        ),
    )

    outcome = fr.rename_transcript_files_with_outcome(
        "old_name", "new_name", str(transcript), dry_run=False
    )
    assert outcome.ok is False
    assert outcome.transaction_committed is True
    assert outcome.finalize_succeeded is False
    assert outcome.partial_success_after_transaction is True

    new_json = transcripts / "new_name.json"
    assert new_json.exists()
    assert not (transcripts / "old_name.json").exists()


def test_rename_transcript_outcome_truth_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Row A: blocked before transaction (invalid managed transcript) — no execute()."""
    outcome_mod = pytest.importorskip(
        "transcriptx.core.utils.file_rename", reason="outcome API"
    )
    if not hasattr(outcome_mod, "rename_transcript_files_with_outcome"):
        pytest.skip("rename_transcript_files_with_outcome not yet implemented")

    t = tmp_path / "a.json"
    t.write_text("{}", encoding="utf-8")
    o = outcome_mod.rename_transcript_files_with_outcome(
        "a", "b", str(t), dry_run=False
    )
    assert o.transaction_attempted is False
    assert o.transaction_succeeded is False
    assert o.transaction_committed is False
    assert o.finalize_attempted is False
    assert o.finalize_succeeded is False
    assert o.ok is False
    assert o.last_error

    # Rows B (execute fails) and C (finalize fails after commit) and D (full success)
    # are covered by test_rename_transaction_execute_failure_skips_finalize,
    # test_rename_finalize_failure_returns_false_without_transaction_rollback,
    # and managed-transcript success paths in this module.
    assert hasattr(o, "finalize_succeeded")


def test_dry_run_skips_finalize_filesystem_and_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """dry_run=True must not run finalize output-dir work or cache invalidation."""
    from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
    from transcriptx.io.transcript_schema import (
        SourceInfo,
        TranscriptMetadata,
        create_transcript_document,
    )

    root = tmp_path / "lib"
    transcripts = root / "transcripts"
    metadata_dir = root / "metadata"
    originals = root / "originals"
    for d in (transcripts, metadata_dir, originals):
        d.mkdir(parents=True)
    (originals / "f.srt").write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata_dir
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR", transcripts
    )

    transcript = transcripts / "old_name.json"
    doc = create_transcript_document(
        [{"speaker": "SPEAKER_00", "text": "Hi", "start": 0.0, "end": 1.0}],
        SourceInfo(
            type="srt",
            original_path="originals/f.srt",
            imported_at="2026-01-01T00:00:00+00:00",
            file_hash="h",
            file_mtime=0.0,
        ),
        TranscriptMetadata(duration_seconds=1.0, segment_count=1, speaker_count=1),
    )
    transcript.write_text(json.dumps(doc), encoding="utf-8")
    write_initial_sidecar(
        transcript,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="f.srt",
        archived_original_relpath="originals/f.srt",
    )

    outputs = tmp_path / "outputs"
    recordings = tmp_path / "recordings"
    outputs.mkdir(parents=True)
    recordings.mkdir(parents=True)
    (outputs / "old_name").mkdir()
    (outputs / "old_name" / "x.txt").write_text("y")

    state_file = tmp_path / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "u1": {
                        "transcript_path": str(transcript),
                        "processed_at": "2020-01-01T00:00:00",
                        "status": "completed",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("transcriptx.core.utils.paths.OUTPUTS_DIR", outputs)
    monkeypatch.setattr("transcriptx.core.utils._path_core.OUTPUTS_DIR", outputs)
    monkeypatch.setattr(fr, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(fr, "RECORDINGS_DIR", recordings)
    monkeypatch.setattr(fr, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE", state_file
    )

    moved = {"v": False}

    def _no_move(*a, **k):
        moved["v"] = True
        raise AssertionError("finalize should not shutil.move under dry_run")

    monkeypatch.setattr(
        "transcriptx.core.utils.rename.journal.STATE_DIR", tmp_path / "state"
    )
    (tmp_path / "state").mkdir(exist_ok=True)
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.pipeline.PROCESSING_STATE_FILE", state_file
    )

    def _no_finalize(*a, **k):
        moved["v"] = True
        raise AssertionError("finalize should not run under dry_run")

    monkeypatch.setattr(
        "transcriptx.core.utils.rename.pipeline.finalize_output_directory_move",
        _no_finalize,
    )

    inv = {"n": 0}

    def _track_inv(*a, **k):
        inv["n"] += 1

    monkeypatch.setattr(
        "transcriptx.core.utils.rename.pipeline.invalidate_path_cache", _track_inv
    )

    assert (
        fr.rename_transcript_files(
            "old_name", "new_name", str(transcript), dry_run=True
        )
        is True
    )
    assert moved["v"] is False
    assert inv["n"] == 0
    assert transcript.name == "old_name.json"
    assert not (outputs / "new_name").exists()


def test_update_processing_state_exact_path_audio_basename_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mp3_path updates via exact Path/basename, not substring replace through parents."""
    from transcriptx.core.utils.processing_state import save_processing_state

    old_tp = tmp_path / "session.json"
    new_tp = tmp_path / "session_new.json"
    old_tp.write_text("{}", encoding="utf-8")
    mp3 = str(tmp_path / "archive" / "old_name_backup" / "old_name.mp3")
    (tmp_path / "archive" / "old_name_backup").mkdir(parents=True)

    state = {
        "processed_files": {
            "k": {
                "processed_at": "2020-01-01T00:00:00",
                "status": "completed",
                "transcript_path": str(old_tp.resolve()),
                "mp3_path": mp3,
                "output_dir_path": str(tmp_path / "out"),
                "canonical_base_name": "session",
            }
        }
    }
    state_file = tmp_path / "processing_state.json"
    save_processing_state(state, state_file)
    outs = tmp_path / "outputs"
    outs.mkdir(parents=True)
    monkeypatch.setattr(fr, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE", state_file
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.processing_state.PROCESSING_STATE_FILE",
        state_file,
    )
    monkeypatch.setattr(fr, "OUTPUTS_DIR", outs)

    fr.update_processing_state(str(old_tp), str(new_tp), "old_name", "new_name")
    loaded = json.loads(state_file.read_text(encoding="utf-8"))
    updated_mp3 = loaded["processed_files"]["k"]["mp3_path"]
    # Only the basename changes; parent dirs are preserved
    assert updated_mp3 == str(tmp_path / "archive" / "old_name_backup" / "new_name.mp3")


def test_ordered_audio_candidate_plan_matches_public_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pure candidate order helper stays aligned with find_original_audio_file."""
    if not hasattr(fr, "ordered_audio_candidate_paths_for_state_entry"):
        pytest.skip("helper not exposed")

    transcript = tmp_path / "m.json"
    transcript.write_text("{}", encoding="utf-8")
    p1 = tmp_path / "1.wav"
    p1.write_bytes(b"x")
    order = fr.ordered_audio_candidate_paths_for_state_entry(
        "f5e5bd96-aef4-4b4a-ad44-5c96aa120337",
        {
            "transcript_path": str(transcript),
            "mp3_path": str(p1),
        },
        str(transcript),
        resolved_audio_from_transcript=None,
        transcript_base="m",
        canonical_base_from_metadata="m",
        base_without_suffix="m",
        recordings_dirs=[tmp_path / "rec"],
        audio_extensions=[".wav", ".mp3"],
    )
    assert order[0] == str(p1)


def test_build_rename_plan_missing_transcript_records_failed_validation(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "nope.json"
    ctx = fr.RenameContext(
        old_name="a",
        new_name="b",
        transcript_path=str(missing),
        transcript_file=missing,
        new_transcript_path=missing.parent / "b.json",
        old_output_dir=tmp_path / "o_old",
        new_output_dir=tmp_path / "o_new",
    )
    plan = fr.build_rename_plan(ctx, None, "2026-04-22T00:00:00")
    assert plan.blocked
    failed = [v for v in plan.validations if not v.passed]
    assert failed
    assert failed[0].name == "transcript_file_exists"


def test_build_rename_plan_unmanaged_transcript_records_managed_validation_failure(
    tmp_path: Path,
) -> None:
    """Bare JSON transcript fails managed validation; plan records the gate."""
    bad = tmp_path / "bare.json"
    bad.write_text("{}", encoding="utf-8")
    ctx = fr.RenameContext(
        old_name="bare",
        new_name="renamed",
        transcript_path=str(bad),
        transcript_file=bad,
        new_transcript_path=bad.parent / "renamed.json",
        old_output_dir=tmp_path / "o_old",
        new_output_dir=tmp_path / "o_new",
    )
    plan = fr.build_rename_plan(ctx, None, "2026-04-22T12:00:00")
    assert plan.blocked
    failed_names = {v.name for v in plan.validations if not v.passed}
    assert "managed_library_transcript" in failed_names


def test_compute_processing_state_rename_mutation_leaves_state_untouched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compute step is read-only on the in-memory ``state`` dict."""
    old_tp = tmp_path / "a.json"
    new_tp = tmp_path / "b.json"
    old_tp.write_text("{}", encoding="utf-8")
    outs = tmp_path / "outputs"
    outs.mkdir()
    monkeypatch.setattr(fr, "OUTPUTS_DIR", outs)

    state = {
        "processed_files": {
            "key1": {
                "processed_at": "2020-01-01T00:00:00",
                "status": "completed",
                "transcript_path": str(old_tp),
                "mp3_path": "",
                "output_dir_path": str(tmp_path / "out"),
                "canonical_base_name": "a",
            }
        }
    }
    before = json.dumps(state, sort_keys=True)
    mut = fr._compute_processing_state_rename_mutation(
        state, str(old_tp), str(new_tp), "a", "b"
    )
    assert mut is not None
    assert mut.entry_key == "key1"
    assert mut.enriched_entry["transcript_path"] == str(new_tp)
    assert json.dumps(state, sort_keys=True) == before


def test_rollback_policy_constant_documents_boundary() -> None:
    assert isinstance(fr.ROLLBACK_POLICY, str)
    assert "execute" in fr.ROLLBACK_POLICY.lower()


def test_rename_transaction_execute_failure_skips_finalize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Truth table: failed transaction — no finalize, no committed transaction."""
    from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
    from transcriptx.io.transcript_schema import (
        SourceInfo,
        TranscriptMetadata,
        create_transcript_document,
    )

    root = tmp_path / "lib"
    transcripts = root / "transcripts"
    metadata_dir = root / "metadata"
    originals = root / "originals"
    for d in (transcripts, metadata_dir, originals):
        d.mkdir(parents=True)
    (originals / "f.srt").write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata_dir
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR", transcripts
    )

    transcript = transcripts / "old_name.json"
    doc = create_transcript_document(
        [{"speaker": "SPEAKER_00", "text": "Hi", "start": 0.0, "end": 1.0}],
        SourceInfo(
            type="srt",
            original_path="originals/f.srt",
            imported_at="2026-01-01T00:00:00+00:00",
            file_hash="h",
            file_mtime=0.0,
        ),
        TranscriptMetadata(duration_seconds=1.0, segment_count=1, speaker_count=1),
    )
    transcript.write_text(json.dumps(doc), encoding="utf-8")
    write_initial_sidecar(
        transcript,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="f.srt",
        archived_original_relpath="originals/f.srt",
    )

    outputs = tmp_path / "outputs"
    recordings = tmp_path / "recordings"
    outputs.mkdir(parents=True)
    recordings.mkdir(parents=True)
    (outputs / "old_name").mkdir()

    state_file = tmp_path / "processing_state.json"
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "u1": {
                        "transcript_path": str(transcript),
                        "processed_at": "2020-01-01T00:00:00",
                        "status": "completed",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("transcriptx.core.utils.paths.OUTPUTS_DIR", outputs)
    monkeypatch.setattr("transcriptx.core.utils._path_core.OUTPUTS_DIR", outputs)
    monkeypatch.setattr(fr, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(fr, "RECORDINGS_DIR", recordings)
    monkeypatch.setattr(fr, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE", state_file
    )

    monkeypatch.setattr(
        "transcriptx.core.utils.rename.journal.STATE_DIR", tmp_path / "state"
    )
    (tmp_path / "state").mkdir(exist_ok=True)
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.pipeline.PROCESSING_STATE_FILE", state_file
    )
    from transcriptx.core.utils.rename_transaction import TransactionResult

    monkeypatch.setattr(
        fr.RenameTransaction,
        "execute",
        lambda self: TransactionResult(
            ok=False,
            failure_code="injected",
            failure_message="injected failure",
        ),
    )

    outcome = fr.rename_transcript_files_with_outcome(
        "old_name", "new_name", str(transcript), dry_run=False
    )
    assert outcome.transaction_attempted is True
    assert outcome.transaction_succeeded is False
    assert outcome.transaction_committed is False
    assert outcome.finalize_attempted is False
    assert outcome.finalize_succeeded is False
    assert outcome.ok is False
    assert transcript.name == "old_name.json"


def test_rename_files_in_directory_warns_on_rename_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    new_dir = tmp_path / "new_name_out"
    new_dir.mkdir(parents=True)
    target = new_dir / "old_name_report.txt"
    target.write_text("z", encoding="utf-8")

    orig_rename = Path.rename

    def selective_rename(self: Path, other: Path) -> Path:
        if self.resolve() == target.resolve():
            raise OSError("simulated rename failure")
        return orig_rename(self, other)

    monkeypatch.setattr(Path, "rename", selective_rename)

    warns = fr.rename_files_in_directory(
        tmp_path / "unused_old", new_dir, "old_name", "new_name"
    )
    assert warns
    assert any("Could not rename" in w for w in warns)


def test_build_rename_plan_target_transcript_collision_records_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_old_name_transcript_env(tmp_path, monkeypatch)
    transcript: Path = env["transcript"]
    (transcript.parent / "new_name.json").write_text("{}", encoding="utf-8")
    new_tp = transcript.parent / "new_name.json"
    ctx = fr.RenameContext(
        old_name="old_name",
        new_name="new_name",
        transcript_path=str(transcript),
        transcript_file=transcript,
        new_transcript_path=new_tp,
        old_output_dir=Path(get_transcript_dir(str(transcript))),
        new_output_dir=Path(get_transcript_dir(str(new_tp))),
    )
    plan = fr.build_rename_plan(
        ctx,
        json.loads(env["state_file"].read_text(encoding="utf-8")),
        "2026-04-22T15:00:00",
    )
    assert plan.blocked
    failed = [v for v in plan.validations if not v.passed]
    assert any(v.name == "target_transcript_path_available" for v in failed)


def test_build_rename_plan_non_blocked_sets_finalize_ops_when_output_dirs_differ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_old_name_transcript_env(tmp_path, monkeypatch)
    transcript: Path = env["transcript"]
    new_tp = transcript.parent / "new_name.json"
    ctx = fr.RenameContext(
        old_name="old_name",
        new_name="new_name",
        transcript_path=str(transcript),
        transcript_file=transcript,
        new_transcript_path=new_tp,
        old_output_dir=Path(get_transcript_dir(str(transcript))),
        new_output_dir=Path(get_transcript_dir(str(new_tp))),
    )
    plan = fr.build_rename_plan(
        ctx,
        json.loads(env["state_file"].read_text(encoding="utf-8")),
        "2026-04-22T15:01:00",
    )
    assert not plan.blocked
    assert plan.needs_output_finalize is True
    assert "output_dir_move" in plan.finalize_ops
    assert any(v.name == "rename_plan_complete" and v.passed for v in plan.validations)


def test_persist_processing_state_mutation_writes_processing_state_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from transcriptx.core.utils.processing_state import save_processing_state

    old_tp = tmp_path / "session.json"
    new_tp = tmp_path / "session_renamed.json"
    old_tp.write_text("{}", encoding="utf-8")
    outs = tmp_path / "outputs"
    outs.mkdir()
    monkeypatch.setattr(fr, "OUTPUTS_DIR", outs)

    state = {
        "processed_files": {
            "k": {
                "processed_at": "2020-01-01T00:00:00",
                "status": "completed",
                "transcript_path": str(old_tp),
                "mp3_path": "",
                "output_dir_path": str(tmp_path / "out"),
                "canonical_base_name": "session",
            }
        }
    }
    state_file = tmp_path / "processing_state.json"
    save_processing_state(state, state_file)

    loaded = json.loads(state_file.read_text(encoding="utf-8"))
    mut = fr._compute_processing_state_rename_mutation(
        loaded, str(old_tp), str(new_tp), "session", "session_renamed"
    )
    assert mut is not None
    fr._persist_processing_state_mutation(loaded, mut, state_file)

    roundtrip = json.loads(state_file.read_text(encoding="utf-8"))
    assert roundtrip["processed_files"]["k"]["transcript_path"] == str(new_tp)


def test_rename_transcript_files_with_outcome_dry_run_not_committed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_old_name_transcript_env(tmp_path, monkeypatch)
    transcript: Path = env["transcript"]
    outcome = fr.rename_transcript_files_with_outcome(
        "old_name", "new_name", str(transcript), dry_run=True
    )
    assert outcome.transaction_succeeded is True
    assert outcome.transaction_committed is False
    assert outcome.finalize_succeeded is True
    assert outcome.ok is True


def test_rename_transcript_outcome_ok_requires_finalize_when_finalize_attempted() -> (
    None
):
    """``ok`` is false if finalize was attempted and did not succeed."""
    o = fr.RenameTranscriptOutcome(
        transaction_attempted=True,
        transaction_succeeded=True,
        transaction_committed=True,
        finalize_attempted=True,
        finalize_succeeded=False,
        last_error="x",
    )
    assert o.ok is False
    assert o.partial_success_after_transaction is True
