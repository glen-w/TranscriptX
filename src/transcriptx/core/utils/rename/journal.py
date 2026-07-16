"""Durable rename journal under state_dir for crash recovery."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import STATE_DIR
from transcriptx.core.utils.rename.io_atomic import write_json_atomic
from transcriptx.core.utils.rename.outcome import RenameError

logger = get_logger()

JOURNAL_SUBDIR = "rename_journal"
JOURNAL_SCHEMA_VERSION = 1


class JournalPhase(str, Enum):
    prepared = "prepared"
    transaction_committed = "transaction_committed"
    finalized = "finalized"
    reconciled = "reconciled"
    complete = "complete"


class JournalLoadError(Exception):
    """Raised when a journal payload is malformed or unsupported."""


@dataclass
class MalformedJournal:
    path: str
    reason: str


@dataclass
class RenameJournalRecord:
    operation_id: str
    phase: str
    old_transcript_path: str
    new_transcript_path: str
    schema_version: int = JOURNAL_SCHEMA_VERSION
    old_output_dir: str = ""
    new_output_dir: str = ""
    artifact_remap_moves: list[list[str]] = field(default_factory=list)
    needs_output_dir_move: bool = False
    output_dir_move_completed: bool = False
    artifact_remap_completed: bool = False
    old_slug: str | None = None
    new_slug: str | None = None
    planned_old_slug: str | None = None
    planned_new_slug: str | None = None
    old_audio_path: str = ""
    new_audio_path: str = ""
    audio_kind: str = ""
    audio_renamed: bool = False
    errors: list[dict[str, str]] = field(default_factory=list)
    error_history: list[dict[str, Any]] = field(default_factory=list)
    repair_attempts: list[dict[str, Any]] = field(default_factory=list)
    repair_attempt_count: int = 0
    last_repair_at: str | None = None
    warnings: list[str] = field(default_factory=list)
    names: dict[str, str] = field(default_factory=dict)
    # Complete transaction plan for prepared-phase classification / repair.
    transaction_file_renames: list[list[str]] = field(default_factory=list)
    staged_json_writes: list[dict[str, Any]] = field(default_factory=list)
    processing_state_file: str = ""
    processing_state_mutation: dict[str, Any] | None = None
    recorded_temps: list[str] = field(default_factory=list)
    processing_state_snapshot: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RenameJournalRecord:
        if not isinstance(data, dict):
            raise JournalLoadError("Journal root must be an object")
        required = (
            "operation_id",
            "phase",
            "old_transcript_path",
            "new_transcript_path",
            "schema_version",
        )
        missing = [k for k in required if k not in data]
        if missing:
            raise JournalLoadError(f"Missing journal fields: {', '.join(missing)}")
        version = data.get("schema_version")
        if version != JOURNAL_SCHEMA_VERSION:
            raise JournalLoadError(f"Unsupported journal schema_version: {version!r}")
        validate_operation_id(str(data["operation_id"]))
        return cls(
            operation_id=str(data["operation_id"]),
            phase=str(data["phase"]),
            old_transcript_path=str(data["old_transcript_path"]),
            new_transcript_path=str(data["new_transcript_path"]),
            schema_version=int(version),
            old_output_dir=str(data.get("old_output_dir") or ""),
            new_output_dir=str(data.get("new_output_dir") or ""),
            artifact_remap_moves=list(data.get("artifact_remap_moves") or []),
            needs_output_dir_move=bool(data.get("needs_output_dir_move")),
            output_dir_move_completed=bool(data.get("output_dir_move_completed")),
            artifact_remap_completed=bool(data.get("artifact_remap_completed")),
            old_slug=data.get("old_slug"),
            new_slug=data.get("new_slug"),
            planned_old_slug=data.get("planned_old_slug"),
            planned_new_slug=data.get("planned_new_slug"),
            old_audio_path=str(data.get("old_audio_path") or ""),
            new_audio_path=str(data.get("new_audio_path") or ""),
            audio_kind=str(data.get("audio_kind") or ""),
            audio_renamed=bool(data.get("audio_renamed")),
            errors=list(data.get("errors") or []),
            error_history=list(data.get("error_history") or []),
            repair_attempts=list(data.get("repair_attempts") or []),
            repair_attempt_count=int(data.get("repair_attempt_count") or 0),
            last_repair_at=data.get("last_repair_at"),
            warnings=list(data.get("warnings") or []),
            names=dict(data.get("names") or {}),
            transaction_file_renames=list(data.get("transaction_file_renames") or []),
            staged_json_writes=list(data.get("staged_json_writes") or []),
            processing_state_file=str(data.get("processing_state_file") or ""),
            processing_state_mutation=data.get("processing_state_mutation"),
            recorded_temps=list(data.get("recorded_temps") or []),
            processing_state_snapshot=data.get("processing_state_snapshot"),
        )


def journal_dir() -> Path:
    return Path(STATE_DIR) / JOURNAL_SUBDIR


def validate_operation_id(operation_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(operation_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise JournalLoadError(
            f"Invalid operation_id (not a UUID): {operation_id!r}"
        ) from exc


def journal_path(operation_id: str) -> Path:
    oid = validate_operation_id(operation_id)
    root = journal_dir().resolve()
    path = (root / f"{oid}.json").resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise JournalLoadError(
            f"Journal path escapes rename_journal directory: {path}"
        ) from exc
    return path


def new_operation_id() -> str:
    return str(uuid.uuid4())


def persist_journal(record: RenameJournalRecord) -> Path:
    path = journal_path(record.operation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, record.to_dict())
    return path


def _safe_persist_journal(record: RenameJournalRecord) -> RenameError | None:
    try:
        persist_journal(record)
        return None
    except Exception as exc:
        logger.error("Failed to persist rename journal: %s", exc)
        return RenameError(
            code="journal_persist_failed",
            message=str(exc),
            phase="journal",
        )


def load_journal(operation_id: str) -> RenameJournalRecord | None:
    try:
        path = journal_path(operation_id)
    except JournalLoadError:
        raise
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return RenameJournalRecord.from_dict(data)


def discover_incomplete_renames() -> tuple[RenameJournalRecord, ...]:
    records, _malformed = discover_incomplete_renames_with_malformed()
    return records


def discover_incomplete_renames_with_malformed() -> (
    tuple[tuple[RenameJournalRecord, ...], tuple[MalformedJournal, ...]]
):
    root = journal_dir()
    if not root.exists():
        return (), ()
    records: list[RenameJournalRecord] = []
    malformed: list[MalformedJournal] = []
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            record = RenameJournalRecord.from_dict(data)
            if record.phase != JournalPhase.complete.value:
                records.append(record)
        except Exception as exc:
            malformed.append(MalformedJournal(path=str(path), reason=str(exc)))
    return tuple(records), tuple(malformed)


def managed_rename_lock_path() -> Path:
    return Path(STATE_DIR) / "managed_rename.lock"


class PreparedOpStatus(str, Enum):
    not_started = "not_started"
    fully_committed = "fully_committed"
    partially_applied = "partially_applied"
    ambiguous = "ambiguous"


def classify_prepared_transaction(
    record: RenameJournalRecord,
) -> PreparedOpStatus:
    """Inspect filesystem against the journaled transaction plan."""
    renames = record.transaction_file_renames
    if not renames:
        # No file renames — treat JSON/state-only as not classifiable without snapshots.
        if record.staged_json_writes or record.processing_state_mutation:
            return PreparedOpStatus.ambiguous
        return PreparedOpStatus.not_started

    statuses: list[PreparedOpStatus] = []
    for item in renames:
        if len(item) < 2:
            statuses.append(PreparedOpStatus.ambiguous)
            continue
        src = Path(item[0])
        dest = Path(item[1])
        src_exists = src.exists()
        dest_exists = dest.exists()
        if src_exists and not dest_exists:
            statuses.append(PreparedOpStatus.not_started)
        elif dest_exists and not src_exists:
            statuses.append(PreparedOpStatus.fully_committed)
        elif src_exists and dest_exists:
            statuses.append(PreparedOpStatus.ambiguous)
        else:
            statuses.append(PreparedOpStatus.partially_applied)

    if all(s == PreparedOpStatus.not_started for s in statuses):
        return PreparedOpStatus.not_started
    if all(s == PreparedOpStatus.fully_committed for s in statuses):
        return PreparedOpStatus.fully_committed
    if any(s == PreparedOpStatus.ambiguous for s in statuses):
        return PreparedOpStatus.ambiguous
    return PreparedOpStatus.partially_applied
