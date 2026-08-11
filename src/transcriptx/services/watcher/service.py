"""Process-level directory watcher supervisor (Streamlit-safe)."""

from __future__ import annotations

import atexit
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.import_admission import is_under_directory, resolve_transcripts_root
from transcriptx.services.watcher.job_store import JobStore
from transcriptx.services.watcher.observer import WatchObserver
from transcriptx.services.watcher.pipeline import process_watched_path
from transcriptx.services.watcher.settings import (
    DirectoryWatcherSettings,
    default_jobs_dir,
    load_watcher_settings,
    save_watcher_settings,
)

logger = get_logger()

_SERVICE_LOCK = threading.RLock()
_SERVICE: DirectoryWatcherService | None = None


@dataclass(frozen=True)
class WatcherStatus:
    running: bool
    enabled: bool
    watch_paths: tuple[str, ...]
    transcript_mode: str
    audio_mode: str
    job_counts: dict[str, int]
    last_errors: tuple[str, ...]
    observer_alive: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "enabled": self.enabled,
            "watch_paths": list(self.watch_paths),
            "transcript_mode": self.transcript_mode,
            "audio_mode": self.audio_mode,
            "job_counts": dict(self.job_counts),
            "last_errors": list(self.last_errors),
            "observer_alive": self.observer_alive,
        }


class DirectoryWatcherService:
    """Singleton supervisor: enqueue on events, drain on a worker thread."""

    def __init__(
        self,
        *,
        settings: DirectoryWatcherSettings | None = None,
        jobs_dir: Path | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._settings = settings or load_watcher_settings()
        self._store = JobStore(jobs_dir or default_jobs_dir())
        self._queue: queue.Queue[Path | None] = queue.Queue()
        self._pending: set[str] = set()
        self._worker: threading.Thread | None = None
        self._observer: WatchObserver | None = None
        self._stop_event = threading.Event()
        self._running = False
        self._last_errors: list[str] = []

    @property
    def settings(self) -> DirectoryWatcherSettings:
        with self._lock:
            return self._settings

    @property
    def store(self) -> JobStore:
        return self._store

    def configure(self, settings: DirectoryWatcherSettings, *, persist: bool = True) -> None:
        errors = settings.validate_for_enable() if settings.enabled else []
        if settings.enabled and errors:
            raise ValueError("; ".join(errors))
        # Always reject managed library paths.
        transcripts_root = resolve_transcripts_root()
        for raw in settings.watch_paths:
            path = Path(raw).expanduser()
            try:
                if path.is_absolute() and is_under_directory(
                    path.resolve(strict=False), transcripts_root
                ):
                    raise ValueError(
                        f"Cannot watch managed transcripts library path: {raw}"
                    )
            except ValueError:
                raise
            except OSError:
                pass
        with self._lock:
            self._settings = settings
            if persist:
                save_watcher_settings(settings)
        if settings.enabled:
            self.start()
        else:
            self.stop()

    def reload(self) -> None:
        settings = load_watcher_settings()
        self.configure(settings, persist=False)

    def start(self) -> list[str]:
        with self._lock:
            settings = self._settings
            if not settings.enabled:
                self._last_errors = ["Watcher is disabled."]
                return list(self._last_errors)
            enable_errors = settings.validate_for_enable()
            if enable_errors:
                self._last_errors = list(enable_errors)
                return list(self._last_errors)

            self.stop_locked()
            self._stop_event.clear()
            self._observer = WatchObserver(
                settings=settings, on_path=self.enqueue_path
            )
            path_errors = self._observer.start()
            self._last_errors = list(path_errors)
            if not self._observer.is_alive:
                self._observer = None
                return list(self._last_errors)

            self._worker = threading.Thread(
                target=self._drain_loop,
                name="transcriptx-watcher-worker",
                daemon=True,
            )
            self._worker.start()
            self._running = True
            logger.info(
                "Directory watcher started on %s",
                ", ".join(settings.watch_paths),
            )
            return list(self._last_errors)

    def stop(self) -> None:
        with self._lock:
            self.stop_locked()

    def stop_locked(self) -> None:
        self._stop_event.set()
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass
        if self._observer is not None:
            self._observer.stop()
            self._observer = None
        worker = self._worker
        self._worker = None
        self._running = False
        if worker is not None and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=5.0)
        with self._lock:
            self._pending.clear()

    def enqueue_path(self, path: Path | str) -> None:
        target = Path(path)
        key = str(target)
        with self._lock:
            if not self._running or self._stop_event.is_set():
                return
            if key in self._pending:
                return
            self._pending.add(key)
        self._queue.put(target)

    def process_path_now(self, path: Path | str) -> Any:
        """Synchronously process one path (tests / manual drain)."""
        return process_watched_path(
            path,
            settings=self.settings,
            store=self._store,
            cancel_check=self._stop_event.is_set,
        )

    def _drain_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                continue
            key = str(item)
            try:
                process_watched_path(
                    item,
                    settings=self.settings,
                    store=self._store,
                    cancel_check=self._stop_event.is_set,
                )
            except Exception:
                logger.exception("Watcher pipeline failed for %s", item)
            finally:
                with self._lock:
                    self._pending.discard(key)

    def status(self) -> WatcherStatus:
        with self._lock:
            settings = self._settings
            running = self._running
            observer_alive = bool(self._observer and self._observer.is_alive)
            errors = tuple(self._last_errors)
        return WatcherStatus(
            running=running and observer_alive,
            enabled=settings.enabled,
            watch_paths=tuple(settings.watch_paths),
            transcript_mode=settings.transcript_mode,
            audio_mode=settings.audio_mode,
            job_counts=self._store.counts_by_state(),
            last_errors=errors,
            observer_alive=observer_alive,
        )


def get_watcher_service() -> DirectoryWatcherService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = DirectoryWatcherService()
            atexit.register(_shutdown_watcher_service)
        return _SERVICE


def _shutdown_watcher_service() -> None:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is not None:
            try:
                _SERVICE.stop()
            except Exception:
                pass
            _SERVICE = None


def reset_watcher_service_for_tests() -> None:
    """Test helper: tear down the process singleton."""
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is not None:
            try:
                _SERVICE.stop()
            except Exception:
                pass
            _SERVICE = None
