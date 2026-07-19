"""Shared pipeline status, error, and schema contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

SCHEMA_VERSION = 1

RunStatus = Literal["succeeded", "partial", "failed", "aborted"]
ModuleStatus = Literal["succeeded", "failed", "skipped", "blocked", "aborted"]
PersistenceSeverity = Literal["required", "optional"]
TranscriptSourceKind = Literal[
    "local_file", "managed_transcript_id", "in_memory_segments", "group_member"
]


class ErrorKind(str, Enum):
    VALIDATION = "validation"
    CONFIG = "config"
    DEPENDENCY = "dependency"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    CANCELLATION = "cancellation"
    CONTEXT = "context"
    INTERNAL = "internal"


class AbortPolicy(str, Enum):
    FAIL_FAST = "fail_fast"
    CONTINUE_ON_ERROR = "continue_on_error"
    ABORT_ON_ERROR_KIND = "abort_on_error_kind"


@dataclass(frozen=True)
class TranscriptSource:
    kind: TranscriptSourceKind
    value: str


@dataclass(frozen=True)
class TranscriptIdentity:
    transcript_identity_hash: str
    transcript_content_hash_full: str
    transcript_file_hash: Optional[str] = None


@dataclass(frozen=True)
class RegistryModuleSnapshot:
    name: str
    dependencies: List[str]
    category: str
    optional_dependencies: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RegistrySnapshot:
    modules: Dict[str, RegistryModuleSnapshot]


@dataclass(frozen=True)
class RunRequest:
    transcript_source: TranscriptSource
    selected_modules: List[str]
    transcript_identity: Optional[TranscriptIdentity] = None
    run_id_override: Optional[str] = None
    output_dir_override: Optional[str] = None
    parallel: bool = False
    max_workers: int = 4
    rerun_mode: str = "new-run"
    persist: bool = False


@dataclass(frozen=True)
class RunIdentity:
    transcript_key: str
    run_id: str
    source_basename: str
    slug: str


@dataclass(frozen=True)
class RunWorkspace:
    output_dir: str


@dataclass(frozen=True)
class RunConfigSnapshot:
    config_hash: str
    config_source: str
    draft_override_applied: bool
    schema_version: int


@dataclass(frozen=True)
class ModuleOutcome:
    module: str
    status: ModuleStatus
    error_kind: Optional[ErrorKind] = None
    reason: Optional[str] = None
    blocking_modules: List[str] = field(default_factory=list)
    duration_ms: Optional[float] = None
    used_cache: bool = False


@dataclass(frozen=True)
class ExecutionPlan:
    requested: List[str]
    runnable: List[str]
    dependency_added: List[str]
    blocked: Dict[str, List[str]]
    skipped_preflight: List[str]
    deterministic_order: List[str]
    plan_hash: str
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True)
class PersistenceOutcome:
    name: str
    success: bool
    severity: PersistenceSeverity
    error_kind: Optional[ErrorKind] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class PersistenceBundle:
    outcomes: List[PersistenceOutcome]


@dataclass
class RunResult:
    status: RunStatus
    execution_status: RunStatus
    final_status: RunStatus
    transcript_path: str
    transcript_key: str
    run_id: str
    output_dir: str
    selected_modules: List[str]
    modules_run: List[str]
    skipped_modules: List[Dict[str, Any]]
    errors: List[str]
    module_results: Dict[str, Any]
    execution_order: List[str]
    cache_hits: List[str]
    duration: float
    summary: Dict[str, Any]
    persistence_outcomes: List[PersistenceOutcome] = field(default_factory=list)
    termination_reason: Optional[str] = None
    schema_version: int = SCHEMA_VERSION
