"""
File locking utilities for safe concurrent access.

Provides cross-platform file locking using fcntl (Unix) or msvcrt (Windows).
When the target file's directory is read-only (e.g. read-only Docker mount),
the lock file is created in a writable temp directory so locking still works.
"""

import hashlib
import tempfile
import time
from pathlib import Path

from transcriptx.core.utils.logger import get_logger

logger = get_logger()

# errno 30 = EROFS (read-only file system)
_ERRNO_EROFS = 30


def _fallback_lock_path(file_path: Path) -> Path:
    """Path for lock file in temp dir when target dir is read-only. Deterministic per file."""
    try:
        resolved = str(file_path.resolve())
    except (OSError, RuntimeError):
        resolved = str(file_path)
    name = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:32] + ".lock"
    return Path(tempfile.gettempdir()) / "transcriptx_locks" / name


# Try to import Windows-specific module
try:
    import msvcrt

    WINDOWS = True
except ImportError:
    WINDOWS = False
    msvcrt = None
    try:
        import fcntl
    except ImportError:
        fcntl = None
        logger.warning("File locking not available on this platform")


class FileLock:
    """
    Context manager for file locking.

    Provides exclusive file locking with timeout support.
    """

    def __init__(self, file_path: Path, timeout: int = 30, blocking: bool = True):
        """
        Initialize file lock.

        Args:
            file_path: Path to file to lock
            timeout: Maximum time to wait for lock (seconds)
            blocking: Whether to block waiting for lock
        """
        self.file_path = file_path
        self.timeout = timeout
        self.blocking = blocking
        self.lock_file = file_path.with_suffix(file_path.suffix + ".lock")
        self.lock_fd = None
        self.acquired = False

    def __enter__(self):
        """Acquire lock."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock."""
        self.release()

    def acquire(self) -> bool:
        """
        Acquire file lock.

        Returns:
            True if lock acquired, False otherwise
        """
        if self.acquired:
            return True

        # Check if locking is available
        if WINDOWS and msvcrt is None:
            logger.warning("File locking not available on Windows")
            return False
        if not WINDOWS and fcntl is None:
            logger.warning("File locking not available (fcntl not available)")
            return False

        lock_path = self.lock_file
        try:
            return self._acquire_at_path(lock_path)
        except OSError as e:
            if getattr(e, "errno", None) != _ERRNO_EROFS:
                raise
            # Target directory is read-only (e.g. Docker read-only mount); use temp dir
            lock_path = _fallback_lock_path(self.file_path)
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(
                "Using fallback lock path (read-only FS): %s -> %s",
                self.lock_file,
                lock_path,
            )
            self.lock_file = lock_path
            return self._acquire_at_path(lock_path)

    def _acquire_at_path(self, lock_path: Path) -> bool:
        """Try to create and acquire lock at the given path. On EROFS, raises OSError."""
        self.lock_file = lock_path
        # Ensure lock file directory exists (may raise EROFS)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_fd = open(lock_path, "w")

        try:
            start_time = time.time()
            while True:
                try:
                    if WINDOWS:
                        msvcrt.locking(self.lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        fcntl.flock(
                            self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                        )

                    self.acquired = True
                    logger.debug(f"Acquired lock: {self.lock_file}")
                    return True

                except (IOError, OSError):
                    if not self.blocking:
                        logger.warning(
                            f"Could not acquire lock (non-blocking): {self.lock_file}"
                        )
                        if self.lock_fd:
                            try:
                                self.lock_fd.close()
                            except OSError:
                                pass
                            self.lock_fd = None
                        return False

                    if time.time() - start_time > self.timeout:
                        logger.error(
                            f"Lock timeout after {self.timeout}s: {self.lock_file}"
                        )
                        if self.lock_fd:
                            try:
                                self.lock_fd.close()
                            except OSError:
                                pass
                            self.lock_fd = None
                        return False

                    time.sleep(0.1)

        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")
            if self.lock_fd:
                try:
                    self.lock_fd.close()
                except OSError as close_err:
                    logger.debug(
                        "Error closing lock fd on acquire failure: %s", close_err
                    )
                self.lock_fd = None
            return False

    def release(self) -> None:
        """Release file lock."""
        if not self.acquired:
            return

        try:
            if self.lock_fd:
                if WINDOWS:
                    msvcrt.locking(self.lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    if fcntl:
                        fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)

                self.lock_fd.close()
                self.lock_fd = None

            # Remove lock file
            if self.lock_file.exists():
                try:
                    self.lock_file.unlink()
                except OSError as unlink_err:
                    logger.debug("Error removing lock file: %s", unlink_err)

            self.acquired = False
            logger.debug(f"Released lock: {self.lock_file}")

        except Exception as e:
            logger.error(f"Error releasing lock: {e}")

    def is_locked(self) -> bool:
        """Check if file is currently locked."""
        # Try to acquire lock non-blocking
        try:
            with open(self.lock_file, "w") as f:
                if WINDOWS:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    if fcntl:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return False
        except (IOError, OSError):
            return True
        except Exception:
            # If locking not available, assume not locked
            return False


def cleanup_stale_locks(lock_file: Path, max_age_seconds: int = 3600) -> None:
    """
    Clean up stale lock files.

    Args:
        lock_file: Path to lock file
        max_age_seconds: Maximum age of lock file before considering stale
    """
    if not lock_file.exists():
        return

    try:
        age = time.time() - lock_file.stat().st_mtime
        if age > max_age_seconds:
            logger.warning(f"Removing stale lock file (age: {age}s): {lock_file}")
            lock_file.unlink()
    except Exception as e:
        logger.error(f"Error cleaning up stale lock: {e}")
