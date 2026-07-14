"""Robustness and edge-case contracts for managed rename (locks, repair, audio, slugs)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.utils.rename.audio_association import (
    AudioAssociationKind,
    classify_audio_path,
    resolve_audio_association,
)
from transcriptx.core.utils.rename.journal import (
    JournalPhase,
    RenameJournalRecord,
    load_journal,
    new_operation_id,
    persist_journal,
)
from transcriptx.core.utils.rename.outcome import RenameStatus
from transcriptx.core.utils.rename.pipeline import (
    rename_managed_transcript,
    repair_managed_rename,
)
from transcriptx.core.utils.rename_transaction import RenameTransaction
from transcriptx.core.utils import slug_manager
from transcriptx.io.speaker_map_resolver import sidecar_path_for

from tests.core.utils.test_rename_managed_contracts import _managed_env


class _LockDenied:
    acquired = False

    def __enter__(self) -> "_LockDenied":
        return self

    def __exit__(self, *_exc) -> bool:
        return False


def test_managed_rename_lock_failure_blocks_without_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.pipeline.FileLock",
        lambda *a, **k: _LockDenied(),
    )
    outcome = rename_managed_transcript(env["transcript"], "renamed")
    assert outcome.status == RenameStatus.blocked
    assert any(e.code == "lock_failed" for e in outcome.errors)
    assert env["transcript"].exists()
    assert not (env["transcripts"] / "renamed.json").exists()


def _state_with_audio(env: dict, audio_path: Path) -> None:
    """Write a schema-valid processing-state row that references audio_path."""
    env["state_file"].write_text(
        json.dumps(
            {
                "processed_files": {
                    "u1": {
                        "transcript_path": str(env["transcript"]),
                        "processed_at": "2020-01-01T00:00:00",
                        "status": "completed",
                        "output_dir_path": str(env["outputs"] / env["canon"]),
                        "mp3_path": str(audio_path),
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def test_failed_rollback_incomplete_when_rollback_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pipeline must surface failed_rollback_incomplete, not failed_rolled_back."""
    env = _managed_env(tmp_path, monkeypatch)
    original = env["transcript"].read_text(encoding="utf-8")
    real_rollback = RenameTransaction.rollback
    real_json = RenameTransaction._execute_json_write
    calls = {"json": 0}

    def fail_first_json_write(self, op):
        calls["json"] += 1
        if calls["json"] == 1:
            return False, "json_write_failed", "simulated sidecar write failure"
        return real_json(self, op)

    def broken_rollback(self):
        result = real_rollback(self)
        result.ok = False
        result.errors.append("simulated incomplete rollback")
        return result

    monkeypatch.setattr(RenameTransaction, "_execute_json_write", fail_first_json_write)
    monkeypatch.setattr(RenameTransaction, "rollback", broken_rollback)
    outcome = rename_managed_transcript(env["transcript"], "rollback_fail")
    assert outcome.status == RenameStatus.failed_rollback_incomplete
    assert "rollback" in (outcome.message or "").lower()
    assert env["transcript"].exists()
    assert env["transcript"].read_text(encoding="utf-8") == original
    assert not (env["transcripts"] / "rollback_fail.json").exists()


def test_working_copy_audio_renamed_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    old_audio = env["recordings"] / "old_name.mp3"
    old_audio.write_bytes(b"audio")
    _state_with_audio(env, old_audio)
    outcome = rename_managed_transcript(env["transcript"], "new_name")
    assert outcome.status == RenameStatus.committed_complete
    assert outcome.audio_renamed is True
    new_audio = env["recordings"] / "new_name.mp3"
    assert new_audio.exists()
    assert not old_audio.exists()


def test_archival_audio_is_not_renamed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    originals = env["transcripts"] / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    archival = originals / "old_name.wav"
    archival.write_bytes(b"wav")
    _state_with_audio(env, archival)
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.audio_association.TRANSCRIPTS_ORIGINALS_DIR",
        originals,
    )
    outcome = rename_managed_transcript(env["transcript"], "new_name")
    assert outcome.status == RenameStatus.committed_complete
    assert outcome.audio_renamed is False
    assert archival.exists()
    assert archival.name == "old_name.wav"
    assert any("archival" in w.lower() or "stable" in w.lower() for w in outcome.warnings)


def test_external_audio_warning_and_no_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    external = tmp_path / "external_media" / "old_name.mp3"
    external.parent.mkdir(parents=True)
    external.write_bytes(b"x")
    _state_with_audio(env, external)
    outcome = rename_managed_transcript(env["transcript"], "new_name")
    assert outcome.status == RenameStatus.committed_complete
    assert outcome.audio_renamed is False
    assert external.exists()
    assert any("external" in w.lower() for w in outcome.warnings)


def test_speaker_map_sidecar_moves_on_managed_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    old_map = sidecar_path_for(env["transcript"])
    old_map.parent.mkdir(parents=True, exist_ok=True)
    old_map.write_text(
        json.dumps({"speaker_map": {"SPEAKER_00": "Alice"}, "ignored_speakers": []}),
        encoding="utf-8",
    )
    outcome = rename_managed_transcript(env["transcript"], "renamed")
    assert outcome.status == RenameStatus.committed_complete
    new_transcript = env["transcripts"] / "renamed.json"
    new_map = sidecar_path_for(new_transcript)
    assert new_map.exists()
    assert not old_map.exists()
    payload = json.loads(new_map.read_text(encoding="utf-8"))
    assert payload["speaker_map"]["SPEAKER_00"] == "Alice"


def test_post_commit_both_absent_output_dirs_is_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.pipeline.finalize_output_directory_move",
        lambda *_a, **_k: "both_absent",
    )
    outcome = rename_managed_transcript(env["transcript"], "partial_out")
    assert outcome.status == RenameStatus.committed_partial
    assert outcome.transaction_committed is True
    assert any(e.code == "output_dir_both_absent" for e in outcome.errors)


def test_repair_prepared_not_started_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr("transcriptx.core.utils.rename.journal.STATE_DIR", state_dir)
    src = tmp_path / "a.json"
    dest = tmp_path / "b.json"
    src.write_text("{}", encoding="utf-8")
    op_id = new_operation_id()
    persist_journal(
        RenameJournalRecord(
            operation_id=op_id,
            phase=JournalPhase.prepared.value,
            old_transcript_path=str(src),
            new_transcript_path=str(dest),
            transaction_file_renames=[[str(src), str(dest), "rename transcript"]],
        )
    )
    outcome = repair_managed_rename(op_id)
    assert outcome.status == RenameStatus.blocked
    assert any(e.code == "prepared_not_started" for e in outcome.errors)


def test_repair_prepared_ambiguous_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr("transcriptx.core.utils.rename.journal.STATE_DIR", state_dir)
    src = tmp_path / "a.json"
    dest = tmp_path / "b.json"
    src.write_text("{}", encoding="utf-8")
    dest.write_text("{}", encoding="utf-8")
    op_id = new_operation_id()
    persist_journal(
        RenameJournalRecord(
            operation_id=op_id,
            phase=JournalPhase.prepared.value,
            old_transcript_path=str(src),
            new_transcript_path=str(dest),
            transaction_file_renames=[[str(src), str(dest), "rename transcript"]],
        )
    )
    outcome = repair_managed_rename(op_id)
    assert outcome.status == RenameStatus.blocked
    assert any(e.code == "prepared_phase_unrecoverable" for e in outcome.errors)


def test_repair_prepared_fully_committed_promotes_and_finishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr("transcriptx.core.utils.rename.journal.STATE_DIR", state_dir)
    src = tmp_path / "a.json"
    dest = tmp_path / "b.json"
    dest.write_text("{}", encoding="utf-8")
    op_id = new_operation_id()
    persist_journal(
        RenameJournalRecord(
            operation_id=op_id,
            phase=JournalPhase.prepared.value,
            old_transcript_path=str(src),
            new_transcript_path=str(dest),
            transaction_file_renames=[[str(src), str(dest), "rename transcript"]],
        )
    )
    outcome = repair_managed_rename(op_id)
    assert outcome.transaction_committed is True
    assert outcome.status in {
        RenameStatus.committed_complete,
        RenameStatus.committed_partial,
    }


def test_repair_prepared_partially_applied_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr("transcriptx.core.utils.rename.journal.STATE_DIR", state_dir)
    src = tmp_path / "a.json"
    dest = tmp_path / "b.json"
    op_id = new_operation_id()
    persist_journal(
        RenameJournalRecord(
            operation_id=op_id,
            phase=JournalPhase.prepared.value,
            old_transcript_path=str(src),
            new_transcript_path=str(dest),
            transaction_file_renames=[[str(src), str(dest), "rename transcript"]],
        )
    )
    outcome = repair_managed_rename(op_id)
    assert outcome.status == RenameStatus.blocked
    assert any(e.code == "prepared_phase_unrecoverable" for e in outcome.errors)
    assert "partially_applied" in (outcome.errors[0].message or "")


def test_repair_increments_attempt_counter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr("transcriptx.core.utils.rename.journal.STATE_DIR", state_dir)
    src = tmp_path / "a.json"
    dest = tmp_path / "b.json"
    dest.write_text("{}", encoding="utf-8")
    op_id = new_operation_id()
    persist_journal(
        RenameJournalRecord(
            operation_id=op_id,
            phase=JournalPhase.transaction_committed.value,
            old_transcript_path=str(src),
            new_transcript_path=str(dest),
            transaction_file_renames=[[str(src), str(dest), "rename transcript"]],
        )
    )
    repair_managed_rename(op_id)
    reloaded = load_journal(op_id)
    assert reloaded is not None
    assert reloaded.repair_attempt_count == 1
    assert len(reloaded.repair_attempts) == 1
    assert reloaded.repair_attempts[0]["from_phase"] == JournalPhase.transaction_committed.value


@pytest.mark.unit
def test_classify_audio_path_recordings_working_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    audio = recordings / "clip.mp3"
    audio.write_bytes(b"x")
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.audio_association.RECORDINGS_DIR", recordings
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.audio_association.OUTPUTS_DIR", tmp_path / "out"
    )
    assoc = classify_audio_path(audio)
    assert assoc.kind == AudioAssociationKind.recordings_working_copy
    assert assoc.renameable is True


@pytest.mark.unit
def test_classify_audio_path_archival_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    originals = tmp_path / "originals"
    originals.mkdir()
    audio = originals / "meet.wav"
    audio.write_bytes(b"x")
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.audio_association.TRANSCRIPTS_ORIGINALS_DIR",
        originals,
    )
    assoc = classify_audio_path(audio)
    assert assoc.kind == AudioAssociationKind.archival_original
    assert assoc.renameable is False


@pytest.mark.unit
def test_resolve_audio_association_none_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.audio_association.find_original_audio_file",
        lambda *_a, **_k: None,
    )
    assoc = resolve_audio_association(transcript, state_snapshot={})
    assert assoc.kind == AudioAssociationKind.none


def _write_index(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_update_index_after_transcript_rename_updates_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index_path = tmp_path / ".transcriptx_index.json"
    monkeypatch.setattr(slug_manager, "INDEX_FILE", index_path)
    old_t = tmp_path / "old_name.json"
    new_t = tmp_path / "new_name.json"
    new_t.write_text("{}", encoding="utf-8")
    key = "sha256:abc"
    _write_index(
        index_path,
        {
            "transcripts": {
                key: {
                    "slug": "old_name",
                    "runs": [],
                    "source_basename": "old_name",
                    "source_path": str(old_t),
                }
            },
            "slug_to_key": {"old_name": key},
        },
    )
    old_slug, new_slug = slug_manager.update_index_after_transcript_rename(
        old_t, new_t
    )
    assert old_slug == "old_name"
    assert new_slug == "new_name"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["transcripts"][key]["source_path"] == str(new_t.resolve())
    assert index["slug_to_key"]["new_name"] == key


def test_update_index_after_transcript_rename_idempotent_when_new_registered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index_path = tmp_path / ".transcriptx_index.json"
    monkeypatch.setattr(slug_manager, "INDEX_FILE", index_path)
    new_t = tmp_path / "already.json"
    new_t.write_text("{}", encoding="utf-8")
    key = "sha256:abc"
    _write_index(
        index_path,
        {
            "transcripts": {
                key: {
                    "slug": "already",
                    "runs": [],
                    "source_basename": "already",
                    "source_path": str(new_t),
                }
            },
            "slug_to_key": {"already": key},
        },
    )
    old_slug, new_slug = slug_manager.update_index_after_transcript_rename(
        tmp_path / "gone.json", new_t
    )
    assert old_slug == "already"
    assert new_slug == "already"


def test_update_index_after_transcript_rename_raises_slug_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index_path = tmp_path / ".transcriptx_index.json"
    monkeypatch.setattr(slug_manager, "INDEX_FILE", index_path)
    old_t = tmp_path / "old_name.json"
    new_t = tmp_path / "new_name.json"
    new_t.write_text("{}", encoding="utf-8")
    other_t = tmp_path / "other_owner.json"
    other_t.write_text("{}", encoding="utf-8")
    current_key = "sha256:current"
    other_key = "sha256:other"
    _write_index(
        index_path,
        {
            "transcripts": {
                current_key: {
                    "slug": "old_name",
                    "runs": [],
                    "source_basename": "old_name",
                    "source_path": str(old_t),
                },
                other_key: {
                    "slug": "new_name",
                    "runs": [],
                    "source_basename": "new_name",
                    "source_path": str(other_t),
                },
            },
            "slug_to_key": {"old_name": current_key, "new_name": other_key},
        },
    )
    with pytest.raises(slug_manager.SlugConflictError):
        slug_manager.update_index_after_transcript_rename(old_t, new_t)


def test_update_index_after_transcript_rename_no_entry_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index_path = tmp_path / ".transcriptx_index.json"
    monkeypatch.setattr(slug_manager, "INDEX_FILE", index_path)
    _write_index(index_path, {"transcripts": {}, "slug_to_key": {}})
    assert slug_manager.update_index_after_transcript_rename(
        tmp_path / "missing.json", tmp_path / "also_missing.json"
    ) == (None, None)
