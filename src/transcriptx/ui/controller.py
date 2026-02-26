from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator

from transcriptx.core.utils.paths import RECORDINGS_DIR

from .io_helpers import (
    format_recording_label,
    save_uploaded_file,
)
from .probes import probe_whispercpp, probe_whisperx


ENGINE_AUTO = "Auto"
ENGINE_WHISPERX = "WhisperX (container)"
ENGINE_WHISPERCPP = "whisper.cpp (planned)"


def list_recordings() -> list[tuple[str, str]]:
    recordings_dir = Path(RECORDINGS_DIR)
    recordings_dir.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[str, str]] = []
    try:
        for entry in recordings_dir.iterdir():
            if entry.is_file():
                entries.append((format_recording_label(entry), str(entry)))
    except OSError:
        return []
    entries.sort(key=lambda item: item[0].lower())
    return entries


def _resolve_input_path(
    uploaded_file, selected_path: str | None
) -> tuple[Path, list[str]]:
    warnings: list[str] = []
    if uploaded_file is not None:
        saved_path, warnings = save_uploaded_file(uploaded_file)
        return saved_path, warnings
    if selected_path:
        path = Path(selected_path)
        if not path.exists():
            raise FileNotFoundError(f"Selected file not found: {path}")
        return path, warnings
    raise ValueError("No input file selected")


def _build_env(model: str | None, language: str | None) -> dict[str, str]:
    env = os.environ.copy()
    if model:
        env["TRANSCRIPTX_MODEL_NAME"] = model
    else:
        env.pop("TRANSCRIPTX_MODEL_NAME", None)
    if language and language.lower() != "auto":
        env["TRANSCRIPTX_LANGUAGE"] = language
    else:
        env.pop("TRANSCRIPTX_LANGUAGE", None)
    return env


def _render_preview(transcript_path: Path, max_lines: int = 30) -> str:
    try:
        with transcript_path.open() as handle:
            data = json.load(handle)
    except Exception as e:
        return f"Could not load transcript: {e}"

    if isinstance(data, dict) and isinstance(data.get("segments"), list):
        segments = data["segments"][:max_lines]
        lines = []
        for seg in segments:
            start = seg.get("start", "")
            end = seg.get("end", "")
            speaker = seg.get("speaker") or "SPEAKER_00"
            text = str(seg.get("text", "")).strip()
            lines.append(f"{speaker} [{start}-{end}]: {text}")
        if not lines:
            return "(No segments found)"
        return "\n".join(lines)
    if isinstance(data, list):
        lines = [str(item) for item in data[:max_lines]]
        return "\n".join(lines) if lines else "(Empty transcript)"
    return "(Unexpected transcript format)"


def run_transcription(
    uploaded_file,
    selected_path: str | None,
    engine_choice: str,
    model_choice: str | None,
    language_choice: str | None,
) -> Generator[tuple[str, str, str, str], None, None]:
    logs = ""
    notes: list[str] = []

    try:
        audio_path, warnings = _resolve_input_path(uploaded_file, selected_path)
        notes.extend(warnings)
    except Exception as e:
        notes.append(str(e))
        yield logs, "", "", "\n".join(notes)
        return

    if engine_choice == ENGINE_WHISPERCPP:
        probe = probe_whispercpp()
        notes.append(probe.detail)
        yield logs, "", "", "\n".join(notes)
        return

    if engine_choice in (ENGINE_AUTO, ENGINE_WHISPERX):
        probe = probe_whisperx()
        if not probe.available:
            notes.append(probe.detail)
            if probe.start_command:
                notes.append(f"Start with: {probe.start_command}")
            yield logs, "", "", "\n".join(notes)
            return

    if engine_choice == ENGINE_WHISPERX:
        engine_arg = "whisperx"
    else:
        engine_arg = "auto"

    env = _build_env(model_choice, language_choice)
    cmd = [
        sys.executable,
        "-m",
        "transcriptx.cli.main",
        "transcribe",
        str(audio_path),
        "--engine",
        engine_arg,
        "--skip-confirm",
        "--print-output-json-path",
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )

    assert process.stderr is not None
    assert process.stdout is not None

    while True:
        line = process.stderr.readline()
        if line:
            logs += line
            yield logs, "", "", "\n".join(notes)
            continue
        if process.poll() is not None:
            break
        time.sleep(0.05)

    remaining_err = process.stderr.read()
    if remaining_err:
        logs += remaining_err

    stdout_value = process.stdout.read().strip()
    return_code = process.returncode or 0

    if return_code != 0:
        notes.append("Transcription failed.")
        yield logs, "", "", "\n".join(notes)
        return

    if not stdout_value:
        notes.append("No transcript path returned from CLI.")
        yield logs, "", "", "\n".join(notes)
        return

    transcript_path = Path(stdout_value)
    if not transcript_path.exists():
        notes.append(f"Transcript path not found: {stdout_value}")
        yield logs, stdout_value, "", "\n".join(notes)
        return

    preview = _render_preview(transcript_path)
    yield logs, stdout_value, preview, "\n".join(notes)
