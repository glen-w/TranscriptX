"""File-backed watcher job records and activity log."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from transcriptx.services.watcher.settings import default_jobs_dir


class JobState(str, Enum):
    DETECTED = "detected"
    STABILIZING = "stabilizing"
    CLASSIFIED = "classified"
    IMPORTING = "importing"
    QUEUED_TRANSCRIPTION = "queued_transcription"
    TRANSCRIBING = "transcribing"
    IMPORTED = "imported"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = frozenset(
    {
        JobState.IMPORTED,
        JobState.SKIPPED,
        JobState.FAILED,
        JobState.CANCELLED,
        JobState.QUEUED_TRANSCRIPTION,
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WatcherJob:
    job_id: str
    path: str
    basename: str
    state: JobState
    kind: str = "ignore"
    detail: str = ""
    st_dev: int | None = None
    st_ino: int | None = None
    size: int | None = None
    mtime_ns: int | None = None
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    transcript_path: str | None = None
    slug: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @staticmethod
    def from_dict(data: dict[str, Any]) -> WatcherJob:
        return WatcherJob(
            job_id=str(data["job_id"]),
            path=str(data["path"]),
            basename=str(data["basename"]),
            state=JobState(str(data["state"])),
            kind=str(data.get("kind") or "ignore"),
            detail=str(data.get("detail") or ""),
            st_dev=data.get("st_dev"),
            st_ino=data.get("st_ino"),
            size=data.get("size"),
            mtime_ns=data.get("mtime_ns"),
            created_at=str(data.get("created_at") or _utc_now()),
            updated_at=str(data.get("updated_at") or _utc_now()),
            transcript_path=data.get("transcript_path"),
            slug=data.get("slug"),
        )


class JobStore:
    """Atomic JSON job records under data_dir/watcher/jobs/."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_jobs_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._activity_path = self.root.parent / "activity.jsonl"

    def _job_path(self, job_id: str) -> Path:
        return self.root / f"{job_id}.json"

    def create(
        self,
        *,
        path: str,
        basename: str,
        state: JobState = JobState.DETECTED,
        kind: str = "ignore",
        detail: str = "",
        st_dev: int | None = None,
        st_ino: int | None = None,
        size: int | None = None,
        mtime_ns: int | None = None,
    ) -> WatcherJob:
        job = WatcherJob(
            job_id=uuid.uuid4().hex[:12],
            path=path,
            basename=basename,
            state=state,
            kind=kind,
            detail=detail,
            st_dev=st_dev,
            st_ino=st_ino,
            size=size,
            mtime_ns=mtime_ns,
        )
        self.write(job)
        self.append_activity(job, event="created")
        return job

    def write(self, job: WatcherJob) -> None:
        with self._lock:
            job.updated_at = _utc_now()
            path = self._job_path(job.job_id)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(job.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tmp.replace(path)

    def update(
        self,
        job: WatcherJob,
        *,
        state: JobState | None = None,
        detail: str | None = None,
        kind: str | None = None,
        transcript_path: str | None = None,
        slug: str | None = None,
        identity: dict[str, int] | None = None,
    ) -> WatcherJob:
        if state is not None:
            job.state = state
        if detail is not None:
            job.detail = detail
        if kind is not None:
            job.kind = kind
        if transcript_path is not None:
            job.transcript_path = transcript_path
        if slug is not None:
            job.slug = slug
        if identity:
            job.st_dev = identity.get("st_dev", job.st_dev)
            job.st_ino = identity.get("st_ino", job.st_ino)
            job.size = identity.get("size", job.size)
            job.mtime_ns = identity.get("mtime_ns", job.mtime_ns)
        self.write(job)
        self.append_activity(job, event="updated")
        return job

    def get(self, job_id: str) -> WatcherJob | None:
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
            return WatcherJob.from_dict(data)
        except (KeyError, TypeError, ValueError):
            return None

    def list_jobs(self, *, limit: int = 100) -> list[WatcherJob]:
        jobs: list[WatcherJob] = []
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
                    jobs.append(WatcherJob.from_dict(data))
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            if len(jobs) >= limit:
                break
        return jobs

    def counts_by_state(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for job in self.list_jobs(limit=1000):
            key = job.state.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def append_activity(self, job: WatcherJob, *, event: str) -> None:
        line = {
            "ts": _utc_now(),
            "event": event,
            "job_id": job.job_id,
            "path": job.path,
            "state": job.state.value,
            "kind": job.kind,
            "detail": job.detail,
        }
        with self._lock:
            self._activity_path.parent.mkdir(parents=True, exist_ok=True)
            with self._activity_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(line, sort_keys=True) + "\n")

    def recent_activity(self, *, limit: int = 50) -> list[dict[str, Any]]:
        if not self._activity_path.is_file():
            return []
        try:
            lines = self._activity_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out: list[dict[str, Any]] = []
        for raw in reversed(lines):
            raw = raw.strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                out.append(data)
            if len(out) >= limit:
                break
        return out
