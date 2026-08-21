"""Typed corpus inventory read-model contracts.

Display strings (✓, —, 31/39, 2d ago) belong in the UI, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class FieldIntegrity(str, Enum):
    OK = "ok"
    MISSING = "missing"
    MALFORMED = "malformed"
    STALE = "stale"


class SpeakerIdStatus(str, Enum):
    NONE = "none"
    PARTIAL = "partial"
    COMPLETE = "complete"
    UNKNOWN = "unknown"


class CorrectionsStatus(str, Enum):
    NEVER_STARTED = "never_started"
    PENDING = "pending"
    COMPLETE = "complete"
    UNKNOWN = "unknown"


class AnalysisStatus(str, Enum):
    UNANALYSED = "unanalysed"
    INCOMPLETE = "incomplete"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class LibraryWorkflowPreset(str, Enum):
    ALL = "all"
    UNANALYSED = "unanalysed"
    NEEDS_SPEAKER_ID = "needs_speaker_id"
    CORRECTIONS_PENDING = "corrections_pending"
    ANALYSED = "analysed"
    FAILED_INCOMPLETE = "failed_incomplete"


class LibrarySort(str, Enum):
    RECENTLY_ADDED = "recently_added"
    RECENTLY_WORKED = "recently_worked"
    NAME = "name"
    DURATION = "duration"
    ANALYSIS_COMPLETION = "analysis_completion"


class ContinueAction(str, Enum):
    CORRECTIONS = "corrections"
    SPEAKER_ID = "speaker_id"
    ANALYSE = "analyse"
    OPEN = "open"


@dataclass(frozen=True)
class LibraryFilter:
    """Navigation and Library toolbar contract."""

    preset: LibraryWorkflowPreset = LibraryWorkflowPreset.ALL
    query: str = ""
    sort: LibrarySort = LibrarySort.RECENTLY_WORKED
    source_id: str | None = None


@dataclass(frozen=True)
class FileStamp:
    """mtime/size fingerprint for one path; size -1 means the path is absent."""

    path: str
    mtime_ns: int
    size: int


@dataclass(frozen=True)
class InventoryFingerprint:
    """Explicit per-transcript invalidation key (stats only, no content)."""

    stamps: tuple[FileStamp, ...]

    def digest(self) -> tuple[tuple[str, int, int], ...]:
        return tuple((s.path, s.mtime_ns, s.size) for s in self.stamps)


@dataclass(frozen=True)
class TranscriptRef:
    """Stable identity for one managed (or discovered) transcript."""

    path: Path
    base_name: str
    slug: str | None = None
    transcript_key: str | None = None


@dataclass(frozen=True)
class SpeakerIdState:
    status: SpeakerIdStatus
    integrity: FieldIntegrity
    named_count: int | None = None
    ignored_count: int | None = None
    unidentified_count: int | None = None


@dataclass(frozen=True)
class CorrectionsState:
    status: CorrectionsStatus
    integrity: FieldIntegrity
    accepted_count: int | None = None
    pending_count: int | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class AnalysisState:
    status: AnalysisStatus
    integrity: FieldIntegrity
    modules_succeeded: int | None = None
    modules_eligible: int | None = None
    latest_run_id: str | None = None
    run_status: str | None = None
    last_analysed_at: datetime | None = None


@dataclass(frozen=True)
class InventoryRow:
    """One corpus inventory row. Identity is path/key, never a table index."""

    transcript_path: Path
    transcript_key: str | None
    slug: str | None
    title: str
    imported_at: datetime | None
    duration_seconds: float | None
    speaker_count: int | None
    word_count: int | None
    source_id: str | None
    listing_integrity: FieldIntegrity
    speaker: SpeakerIdState
    corrections: CorrectionsState
    analysis: AnalysisState
    last_activity_at: datetime | None
    fingerprint: InventoryFingerprint = field(repr=False)


@dataclass(frozen=True)
class InventoryBuildStats:
    """Diagnostics for tests: rebuilds and content reads, not UI."""

    row_count: int
    rows_rebuilt: int
    content_reads: int
    cache_hits: int
