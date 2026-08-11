"""watchdog observer + per-path debounce enqueue."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from transcriptx.core.utils.logger import get_logger
from transcriptx.services.watcher.classifier import WatchKind, classify_path
from transcriptx.services.watcher.settings import DirectoryWatcherSettings

logger = get_logger()


class _DebouncedHandler(FileSystemEventHandler):
    def __init__(
        self,
        *,
        settings: DirectoryWatcherSettings,
        on_path: Callable[[Path], None],
    ) -> None:
        super().__init__()
        self._settings = settings
        self._on_path = on_path
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        # Dest path is the interesting one for inbox drops via rename/move.
        dest = getattr(event, "dest_path", None)
        if dest:
            self._schedule(Path(str(dest)))

    def _handle(self, event: FileSystemEvent) -> None:
        if getattr(event, "is_directory", False):
            return
        src = getattr(event, "src_path", None)
        if not src:
            return
        self._schedule(Path(str(src)))

    def _schedule(self, path: Path) -> None:
        if classify_path(path, self._settings) is WatchKind.IGNORE:
            return
        key = str(path)
        delay = max(self._settings.debounce_ms, 100) / 1000.0

        def _fire() -> None:
            with self._lock:
                self._timers.pop(key, None)
            try:
                self._on_path(path)
            except Exception:
                logger.exception("Watcher enqueue failed for %s", path)

        with self._lock:
            existing = self._timers.get(key)
            if existing is not None:
                existing.cancel()
            timer = threading.Timer(delay, _fire)
            timer.daemon = True
            self._timers[key] = timer
            timer.start()

    def cancel_all(self) -> None:
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()


class WatchObserver:
    """Lifecycle wrapper around watchdog Observer."""

    def __init__(
        self,
        *,
        settings: DirectoryWatcherSettings,
        on_path: Callable[[Path], None],
    ) -> None:
        self._settings = settings
        self._on_path = on_path
        self._handler = _DebouncedHandler(settings=settings, on_path=on_path)
        self._observer: Observer | None = None

    @property
    def is_alive(self) -> bool:
        return bool(self._observer and self._observer.is_alive())

    def start(self) -> list[str]:
        """Start watching configured paths. Returns user-safe path errors."""
        self.stop()
        errors: list[str] = []
        observer = Observer()
        scheduled = 0
        for raw in self._settings.watch_paths:
            path = Path(raw).expanduser()
            if not path.is_absolute():
                errors.append(f"Watch path must be absolute: {raw}")
                continue
            if not path.exists() or not path.is_dir():
                errors.append(f"Watch path missing or not a directory: {raw}")
                continue
            try:
                observer.schedule(
                    self._handler,
                    str(path),
                    recursive=bool(self._settings.recursive),
                )
                scheduled += 1
            except Exception as exc:
                errors.append(f"Could not watch {raw}: {exc}")
        if scheduled == 0:
            observer = None  # type: ignore[assignment]
            return errors or ["No valid watch paths."]
        observer.start()
        self._observer = observer
        return errors

    def stop(self) -> None:
        self._handler.cancel_all()
        observer = self._observer
        self._observer = None
        if observer is None:
            return
        try:
            observer.stop()
            observer.join(timeout=5.0)
        except Exception:
            logger.exception("Error stopping watcher observer")
