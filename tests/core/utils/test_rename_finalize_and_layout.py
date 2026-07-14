"""Unit coverage for rename finalize, journal classification, and sidecar layout."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.utils.rename.finalize import (
    ArtifactRemapPlan,
    cleanup_abandoned_temps,
    execute_artifact_remap,
    finalize_output_directory_move,
)
from transcriptx.core.utils.rename.journal import (
    JournalPhase,
    PreparedOpStatus,
    RenameJournalRecord,
    classify_prepared_transaction,
    new_operation_id,
)
from transcriptx.core.utils.rename.plan import preflight_transaction_rename_map
from transcriptx.core.utils.rename.sidecars import (
    ImportSidecarLayout,
    resolve_import_sidecar_layout,
    unique_quarantine_path,
)


@pytest.mark.unit
def test_finalize_output_dir_already_done_is_idempotent(tmp_path: Path) -> None:
    old_dir = tmp_path / "old_out"
    new_dir = tmp_path / "new_out"
    new_dir.mkdir()
    (new_dir / "a.txt").write_text("x")
    status = finalize_output_directory_move(old_dir, new_dir)
    assert status == "already_done"


@pytest.mark.unit
def test_finalize_output_dir_both_absent(tmp_path: Path) -> None:
    status = finalize_output_directory_move(
        tmp_path / "missing_a", tmp_path / "missing_b"
    )
    assert status == "both_absent"


@pytest.mark.unit
def test_finalize_output_dir_merge_when_both_exist(tmp_path: Path) -> None:
    old_dir = tmp_path / "old_out"
    new_dir = tmp_path / "new_out"
    old_dir.mkdir()
    new_dir.mkdir()
    (old_dir / "left.txt").write_text("L")
    (new_dir / "right.txt").write_text("R")
    status = finalize_output_directory_move(old_dir, new_dir)
    assert status == "completed"
    assert (new_dir / "left.txt").exists()
    assert (new_dir / "right.txt").exists()
    assert not old_dir.exists() or not any(old_dir.iterdir())


@pytest.mark.unit
def test_artifact_remap_treats_planned_pair_as_already_done(tmp_path: Path) -> None:
    src = tmp_path / "old_a.txt"
    dest = tmp_path / "new_a.txt"
    dest.write_text("done")
    plan = ArtifactRemapPlan(moves=((src, dest),))
    errors = execute_artifact_remap(plan)
    assert errors == []
    assert dest.read_text() == "done"


@pytest.mark.unit
def test_artifact_remap_reports_missing_source(tmp_path: Path) -> None:
    src = tmp_path / "gone.txt"
    dest = tmp_path / "dest.txt"
    plan = ArtifactRemapPlan(moves=((src, dest),))
    errors = execute_artifact_remap(plan)
    assert errors
    assert "missing" in errors[0].lower()


@pytest.mark.unit
def test_cleanup_abandoned_temps_is_operation_scoped(tmp_path: Path) -> None:
    recorded = tmp_path / ".tx_rename_tmp_op1_file"
    other = tmp_path / ".tx_rename_tmp_other"
    recorded.write_text("a")
    other.write_text("b")
    cleaned = cleanup_abandoned_temps(
        roots=[tmp_path],
        recorded_temps=[str(recorded)],
    )
    assert str(recorded) in cleaned
    assert not recorded.exists()
    assert other.exists()


@pytest.mark.unit
def test_cleanup_abandoned_temps_skips_broad_scan_without_recorded(
    tmp_path: Path,
) -> None:
    orphan = tmp_path / ".tx_rename_tmp_orphan"
    orphan.write_text("x")
    cleaned = cleanup_abandoned_temps(roots=[tmp_path])
    assert cleaned == []
    assert orphan.exists()


@pytest.mark.unit
def test_classify_prepared_not_started(tmp_path: Path) -> None:
    src = tmp_path / "a.json"
    dest = tmp_path / "b.json"
    src.write_text("{}")
    record = RenameJournalRecord(
        operation_id=new_operation_id(),
        phase=JournalPhase.prepared.value,
        old_transcript_path=str(src),
        new_transcript_path=str(dest),
        transaction_file_renames=[[str(src), str(dest), "rename"]],
    )
    assert classify_prepared_transaction(record) == PreparedOpStatus.not_started


@pytest.mark.unit
def test_classify_prepared_fully_committed(tmp_path: Path) -> None:
    src = tmp_path / "a.json"
    dest = tmp_path / "b.json"
    dest.write_text("{}")
    record = RenameJournalRecord(
        operation_id=new_operation_id(),
        phase=JournalPhase.prepared.value,
        old_transcript_path=str(src),
        new_transcript_path=str(dest),
        transaction_file_renames=[[str(src), str(dest), "rename"]],
    )
    assert classify_prepared_transaction(record) == PreparedOpStatus.fully_committed


@pytest.mark.unit
def test_classify_prepared_ambiguous_when_both_exist(tmp_path: Path) -> None:
    src = tmp_path / "a.json"
    dest = tmp_path / "b.json"
    src.write_text("{}")
    dest.write_text("{}")
    record = RenameJournalRecord(
        operation_id=new_operation_id(),
        phase=JournalPhase.prepared.value,
        old_transcript_path=str(src),
        new_transcript_path=str(dest),
        transaction_file_renames=[[str(src), str(dest), "rename"]],
    )
    assert classify_prepared_transaction(record) == PreparedOpStatus.ambiguous


@pytest.mark.unit
def test_preflight_detects_duplicate_destinations(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    dest = tmp_path / "shared.txt"
    msg = preflight_transaction_rename_map([(a, dest, "one"), (b, dest, "two")])
    assert msg is not None
    assert "multiple sources" in msg.lower()


@pytest.mark.unit
def test_unique_quarantine_paths_differ(tmp_path: Path) -> None:
    legacy = tmp_path / "stem.import_meta.json"
    legacy.write_text("{}")
    q1 = unique_quarantine_path(legacy)
    q2 = unique_quarantine_path(legacy)
    assert q1 != q2
    assert q1.parent == legacy.parent
    assert q1.name.startswith(".quarantine_")


@pytest.mark.unit
def test_resolve_import_sidecar_both_identical_and_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    metadata = transcripts / "metadata"
    transcripts.mkdir()
    metadata.mkdir()
    monkeypatch.setattr(
        "transcriptx.io.import_metadata_sidecar.DIARISED_TRANSCRIPTS_DIR", transcripts
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata_sidecar.TRANSCRIPTS_METADATA_DIR", metadata
    )
    t = transcripts / "meet.json"
    t.write_text("{}")

    from transcriptx.io.import_metadata_sidecar import (
        legacy_flat_sidecar_path_for_transcript,
        mirrored_import_sidecar_path_for_transcript,
    )

    mirrored = mirrored_import_sidecar_path_for_transcript(t)
    legacy = legacy_flat_sidecar_path_for_transcript(t)
    mirrored.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"schema_version": 1, "x": 1})
    mirrored.write_text(payload)
    legacy.write_text(payload)
    identical = resolve_import_sidecar_layout(t)
    assert identical.layout == ImportSidecarLayout.both_identical
    assert identical.warning

    legacy.write_text(json.dumps({"schema_version": 1, "x": 2}))
    ambiguous = resolve_import_sidecar_layout(t)
    assert ambiguous.layout == ImportSidecarLayout.ambiguous
    assert ambiguous.block_message
