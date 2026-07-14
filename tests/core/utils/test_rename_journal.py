"""Journal schema, UUID/path safety, and malformed discovery."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.utils.rename.journal import (
    JOURNAL_SCHEMA_VERSION,
    JournalLoadError,
    JournalPhase,
    RenameJournalRecord,
    discover_incomplete_renames_with_malformed,
    journal_path,
    load_journal,
    new_operation_id,
    persist_journal,
    validate_operation_id,
)


@pytest.fixture
def journal_root(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.journal.STATE_DIR", tmp_path / "state"
    )
    (tmp_path / "state").mkdir()
    return tmp_path / "state"


def _minimal_record(operation_id: str | None = None) -> RenameJournalRecord:
    return RenameJournalRecord(
        operation_id=operation_id or new_operation_id(),
        phase=JournalPhase.prepared.value,
        old_transcript_path="/old.json",
        new_transcript_path="/new.json",
        schema_version=JOURNAL_SCHEMA_VERSION,
    )


def test_journal_schema_roundtrip(journal_root):
    record = _minimal_record()
    persist_journal(record)
    loaded = load_journal(record.operation_id)
    assert loaded is not None
    assert loaded.schema_version == JOURNAL_SCHEMA_VERSION


def test_unsupported_schema_rejected(journal_root):
    oid = new_operation_id()
    path = journal_path(oid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "operation_id": oid,
                "phase": "prepared",
                "old_transcript_path": "a",
                "new_transcript_path": "b",
                "schema_version": 999,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(JournalLoadError, match="Unsupported"):
        load_journal(oid)


def test_invalid_uuid_rejected(journal_root):
    with pytest.raises(JournalLoadError, match="UUID"):
        validate_operation_id("../evil")
    with pytest.raises(JournalLoadError, match="UUID"):
        journal_path("../../etc/passwd")


def test_path_traversal_operation_id_rejected(journal_root):
    with pytest.raises(JournalLoadError):
        journal_path("not-a-uuid")


def test_discover_reports_malformed_separately(journal_root):
    good = _minimal_record()
    persist_journal(good)
    bad = journal_root / "rename_journal" / "broken.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not json", encoding="utf-8")
    incomplete, malformed = discover_incomplete_renames_with_malformed()
    assert any(r.operation_id == good.operation_id for r in incomplete)
    assert any("broken.json" in m.path for m in malformed)
