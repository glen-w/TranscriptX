"""File-backed transcription job records (durable across Streamlit reruns)."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from transcriptx.core.utils.paths import PATHS

_MAX_LOGS = 40


class TranscriptionJobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = frozenset(
    {
        TranscriptionJobState.SUCCEEDED,
        TranscriptionJobState.FAILED,
        TranscriptionJobState.CANCELLED,
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_transcription_jobs_dir(*, data_dir: Path | None = None) -> Path:
    root = Path(data_dir) if data_dir is not None else Path(PATHS.data_dir)
    return root / "transcription" / "jobs"


@dataclass
class TranscriptionJob:
    job_id: str
    state: TranscriptionJobState
    provider_id: str
    input_paths: list[str]
    model: str = ""
    language: str = ""
    diarize: bool = False
    import_into_library: bool = True
    output_dir: str | None = None
    cancel_requested: bool = False
    progress_message: str = ""
    progress_pct: float | None = None
    logs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    succeeded_count: int = 0
    failed_count: int = 0
    imported_paths: list[str] = field(default_factory=list)
    watcher_job_id: str | None = None
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @staticmethod
    def from_dict(data: dict[str, Any]) -> TranscriptionJob:
        return TranscriptionJob(
            job_id=str(data["job_id"]),
            state=TranscriptionJobState(str(data["state"])),
            provider_id=str(data.get("provider_id") or ""),
            input_paths=[str(p) for p in (data.get("input_paths") or [])],
            model=str(data.get("model") or ""),
            language=str(data.get("language") or ""),
            diarize=bool(data.get("diarize")),
            import_into_library=bool(data.get("import_into_library", True)),
            output_dir=data.get("output_dir"),
            cancel_requested=bool(data.get("cancel_requested")),
            progress_message=str(data.get("progress_message") or ""),
            progress_pct=data.get("progress_pct"),
            logs=[str(x) for x in (data.get("logs") or [])][-_MAX_LOGS:],
            errors=[str(x) for x in (data.get("errors") or [])],
            succeeded_count=int(data.get("succeeded_count") or 0),
            failed_count=int(data.get("failed_count") or 0),
            imported_paths=[str(p) for p in (data.get("imported_paths") or [])],
            watcher_job_id=data.get("watcher_job_id"),
            created_at=str(data.get("created_at") or _utc_now()),
            updated_at=str(data.get("updated_at") or _utc_now()),
            duration_seconds=float(data.get("duration_seconds") or 0.0),
        )


class TranscriptionJobStore:
    """Atomic JSON job records under data_dir/transcription/jobs/."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_transcription_jobs_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _job_path(self, job_id: str) -> Path:
        return self.root / f"{job_id}.json"

    def create(
        self,
        *,
        provider_id: str,
        input_paths: list[str],
        model: str = "",
        language: str = "",
        diarize: bool = False,
        import_into_library: bool = True,
        output_dir: str | None = None,
        watcher_job_id: str | None = None,
        job_id: str | None = None,
    ) -> TranscriptionJob:
        job = TranscriptionJob(
            job_id=job_id or uuid.uuid4().hex[:12],
            state=TranscriptionJobState.QUEUED,
            provider_id=provider_id,
            input_paths=list(input_paths),
            model=model,
            language=language,
            diarize=diarize,
            import_into_library=import_into_library,
            output_dir=output_dir,
            watcher_job_id=watcher_job_id,
        )
        self.write(job)
        return job

    def write(self, job: TranscriptionJob) -> None:
        with self._lock:
            job.updated_at = _utc_now()
            path = self._job_path(job.job_id)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(job.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tmp.replace(path)

    def update(self, job: TranscriptionJob, **changes: Any) -> TranscriptionJob:
        for key, value in changes.items():
            if key == "logs" and isinstance(value, list):
                setattr(job, key, value[-_MAX_LOGS:])
            else:
                setattr(job, key, value)
        self.write(job)
        return job

    def append_log(self, job: TranscriptionJob, message: str) -> TranscriptionJob:
        logs = list(job.logs)
        logs.append(message)
        return self.update(job, logs=logs[-_MAX_LOGS:], progress_message=message)

    def request_cancel(self, job_id: str) -> TranscriptionJob | None:
        job = self.get(job_id)
        if job is None:
            return None
        if job.state in TERMINAL_STATES:
            return job
        return self.update(job, cancel_requested=True)

    def get(self, job_id: str) -> TranscriptionJob | None:
        path = self._job_path(job_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        try:
            return TranscriptionJob.from_dict(data)
        except (KeyError, TypeError, ValueError):
            return None

    def list_jobs(self, *, limit: int = 50) -> list[TranscriptionJob]:
        jobs: list[TranscriptionJob] = []
        try:
            paths = sorted(
                self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
            )
        except OSError:
            return []
        for path in paths:
            if path.name.endswith(".tmp"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    jobs.append(TranscriptionJob.from_dict(data))
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            if len(jobs) >= limit:
                break
        return jobs
