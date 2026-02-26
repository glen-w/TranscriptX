"""Persistent mpv player wrapper for fast segment playback."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def check_mpv_available() -> Tuple[bool, Optional[str]]:
    """Check if mpv is available on the system."""
    mpv_path = shutil.which("mpv")
    if not mpv_path:
        return False, "mpv is not installed or not in PATH"
    try:
        result = subprocess.run(
            [mpv_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return True, None
        return False, f"mpv command failed (exit code: {result.returncode})"
    except subprocess.TimeoutExpired:
        return False, "mpv check timed out"
    except Exception as exc:
        return False, f"Error checking mpv: {exc}"


class MPVPlayer:
    """Manage a persistent mpv process and control it via IPC."""

    def __init__(self, ipc_path: Optional[Path] = None) -> None:
        self._ipc_path = Path(ipc_path or f"/tmp/transcriptx-mpv-{os.getpid()}.sock")
        self._proc: Optional[subprocess.Popen] = None
        self._current_file: Optional[Path] = None
        self._stop_timer: Optional[threading.Timer] = None

    def start(self) -> bool:
        if self._proc and self._proc.poll() is None:
            return True

        mpv_path = shutil.which("mpv")
        if not mpv_path:
            return False

        if self._ipc_path.exists():
            try:
                self._ipc_path.unlink()
            except OSError:
                pass

        cmd = [
            mpv_path,
            "--idle=yes",
            "--no-terminal",
            "--no-video",
            f"--input-ipc-server={self._ipc_path}",
        ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as exc:
            logger.warning(f"Failed to start mpv: {exc}")
            self._proc = None
            return False

        # Wait briefly for IPC socket to appear
        for _ in range(40):
            if self._ipc_path.exists():
                return True
            if self._proc.poll() is not None:
                break
            time.sleep(0.05)

        self.stop()
        return False

    def is_running(self) -> bool:
        return (
            self._proc is not None
            and self._proc.poll() is None
            and self._ipc_path.exists()
        )

    def stop(self) -> None:
        self._cancel_timer()
        self._pause()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None
        self._current_file = None
        if self._ipc_path.exists():
            try:
                self._ipc_path.unlink()
            except OSError:
                pass

    def play_segment(self, audio_path: Path, start: float, duration: float) -> bool:
        if not self.start():
            return False

        try:
            if self._current_file != audio_path:
                self._send_command(["loadfile", str(audio_path), "replace"])
                self._current_file = audio_path

            self._send_command(["set_property", "pause", "yes"])
            self._send_command(["seek", float(start), "absolute"])
            self._send_command(["set_property", "ab-loop-a", float(start)])
            self._send_command(["set_property", "ab-loop-b", float(start + duration)])
            self._send_command(["set_property", "pause", "no"])
            self._schedule_stop(duration)
            return True
        except Exception as exc:
            logger.warning(f"mpv playback failed: {exc}")
            return False

    def pause(self) -> None:
        self._cancel_timer()
        self._pause()

    def _pause(self) -> None:
        try:
            self._send_command(["set_property", "pause", "yes"])
            self._send_command(["set_property", "ab-loop-a", "no"])
            self._send_command(["set_property", "ab-loop-b", "no"])
        except Exception:
            pass

    def _schedule_stop(self, duration: float) -> None:
        self._cancel_timer()
        delay = max(0.05, float(duration))
        self._stop_timer = threading.Timer(delay, self.pause)
        self._stop_timer.daemon = True
        self._stop_timer.start()

    def _cancel_timer(self) -> None:
        if self._stop_timer:
            self._stop_timer.cancel()
            self._stop_timer = None

    def _send_command(self, command: list) -> None:
        payload = json.dumps({"command": command}).encode("utf-8") + b"\n"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(self._ipc_path))
            sock.sendall(payload)
