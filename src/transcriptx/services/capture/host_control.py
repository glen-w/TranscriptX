"""Spawn the G5 host companion from native-Mac GUI code (never Compose)."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from transcriptx.core.observability.hardware_probe import detect_in_container
from transcriptx.core.utils.paths import PATHS


@dataclass(frozen=True)
class CaptureCommandResult:
    returncode: int
    stdout: str
    stderr: str


def capture_script_path() -> Path:
    return PATHS.project_root / "scripts" / "system-audio-capture.py"


def capture_controls_available() -> bool:
    """True when Transcribe Audio may show Start/Stop (native Mac host)."""
    if sys.platform != "darwin":
        return False
    if detect_in_container():
        return False
    return capture_script_path().is_file()


def _base_cmd() -> list[str]:
    script = capture_script_path()
    recordings = Path(PATHS.recordings_dir) / "capture"
    transcripts = Path(PATHS.transcripts_dir) / "originals"
    sessions = Path(PATHS.data_dir) / "capture" / "sessions"
    return [
        sys.executable,
        str(script),
        "--recordings",
        str(recordings),
        "--transcripts",
        str(transcripts),
        "--sessions-dir",
        str(sessions),
    ]


def _run(args: list[str], *, timeout: int = 30) -> CaptureCommandResult:
    proc = subprocess.run(
        _base_cmd() + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CaptureCommandResult(
        returncode=int(proc.returncode),
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def start_capture(*, title: str = "", mix_mic: bool = False) -> CaptureCommandResult:
    extra: list[str] = ["start"]
    if title.strip():
        extra.extend(["--name", title.strip()])
    if mix_mic:
        extra.append("--mix-mic")
    return _run(extra, timeout=60)


def stop_capture(
    *, admit: bool = False, transcribe: bool = True
) -> CaptureCommandResult:
    extra = ["stop"]
    if admit:
        extra.append("--admit")
    if not transcribe:
        extra.append("--no-transcribe")
    return _run(extra, timeout=3600)


def list_capture_status() -> dict | None:
    result = _run(["status", "--json"], timeout=15)
    if not result.stdout.strip():
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "raw": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    if isinstance(data, dict) and "session_id" in data:
        return data
    if isinstance(data, dict) and data.get("session") is None:
        return None
    return data if isinstance(data, dict) else None
