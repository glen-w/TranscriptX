#!/usr/bin/env python3
"""
Host-side Mac system-audio capture (roadmap G5).

BlackHole / Multi-Output Device → WAV session → on Stop convert to 16 kHz
mono 64k MP3 (same as inbox-watch) → whispermlx JSON under originals/ →
optional python -m transcriptx.admit_originals.

Sibling of inbox-watch / voice-note-watch. Not a meeting bot. Not inside
the Linux analysis Compose image. Streamlit never embeds ffmpeg; a native
Mac Transcribe Audio panel may spawn this script for start/stop.

Does not import the transcriptx package. Admit is a subprocess.

Install:
    install -m 755 scripts/system-audio-capture.py ~/.local/bin/system-audio-capture

Config (merge order: portable defaults <- env <- local JSON <- CLI):
    --config /path/to/config.json
    or env SYSTEM_AUDIO_CAPTURE_CONFIG
    default: .transcriptx/system-audio-capture.json when run from the repo

    Example: config/system-audio-capture.example.json
    Env prefix is SYSTEM_AUDIO_CAPTURE_* only, so INBOX_WATCH_ADMIT cannot
    turn admission on.

Do not attach this to the login agent that runs inbox-watch --watch.
Do not use a KeepAlive LaunchAgent (always-on system-audio recording).

Exit 0 = ok; 1 = runtime failure; 2 = CLI/config/validation error.
"""

from __future__ import annotations

import argparse
import audioop
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
import wave
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

CONFIG_VERSION = 1
CONFIG_ENV_VAR = "SYSTEM_AUDIO_CAPTURE_CONFIG"
ALLOW_NON_DARWIN_ENV = "SYSTEM_AUDIO_CAPTURE_ALLOW_NON_DARWIN"
SESSION_SCHEMA_VERSION = 1
TEMP_DIR_NAME = ".whispermlx-system-audio"

RECORDING_STATES = frozenset({"recording", "stopping"})
TERMINAL_STATES = frozenset(
    {"admitted", "transcribed", "recorded", "failed", "abandoned"}
)

_AUDIO_HEADER = re.compile(r"AVFoundation audio devices", re.I)
_VIDEO_HEADER = re.compile(r"AVFoundation video devices", re.I)
_DEV_LINE = re.compile(r"\[(\d+)\]\s+(.+)$")

KNOWN_CONFIG_KEYS = frozenset(
    {
        "version",
        "recordings",
        "transcripts",
        "sessions_dir",
        "env_file",
        "whispermlx",
        "ffmpeg",
        "model",
        "language",
        "device",
        "mix_mic_device",
        "admit_python",
        "library_inbox",
        "watcher_inbox",
        "voice_note_inbox",
        "max_duration_seconds",
        "min_free_bytes",
        "silent_input_seconds",
        "silent_rms_threshold",
    }
)

_PATH_KEYS = (
    "recordings",
    "transcripts",
    "sessions_dir",
    "env_file",
    "whispermlx",
    "ffmpeg",
    "admit_python",
    "library_inbox",
    "watcher_inbox",
    "voice_note_inbox",
)


def _load_inbox_watch():
    path = Path(__file__).resolve().parent / "inbox-watch.py"
    spec = importlib.util.spec_from_file_location("inbox_watch_host", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"ERROR: cannot load inbox-watch helpers from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["inbox_watch_host"] = module
    spec.loader.exec_module(module)
    return module


iw = _load_inbox_watch()


def _log(msg: str = "", *, err: bool = False) -> None:
    print(msg, file=sys.stderr if err else sys.stdout)


def find_repo_root() -> Path | None:
    return iw.find_repo_root()


def allow_non_darwin() -> bool:
    raw = (os.environ.get(ALLOW_NON_DARWIN_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def require_darwin() -> str | None:
    if sys.platform == "darwin" or allow_non_darwin():
        return None
    return (
        "system-audio-capture is macOS-only (BlackHole / avfoundation). "
        "Compose Linux cannot see Mac loopback. Run this on the Mac host."
    )


@dataclass
class EffectiveConfig:
    recordings: Path | None
    transcripts: Path | None
    sessions_dir: Path | None
    env_file: Path | None
    whispermlx: Path | None
    ffmpeg: Path | None
    admit_python: Path | None
    library_inbox: Path | None
    watcher_inbox: Path | None
    voice_note_inbox: Path | None
    model: str
    language: str
    device: str
    mix_mic_device: str
    max_duration_seconds: int
    min_free_bytes: int
    silent_input_seconds: int
    silent_rms_threshold: int


@dataclass
class CaptureSession:
    session_id: str
    state: str
    title: str = ""
    device: str = ""
    mix_mic: str = ""
    started_at: str = ""
    stopped_at: str | None = None
    wav_path: str = ""
    mp3_path: str | None = None
    json_path: str | None = None
    ffmpeg_pid: int | None = None
    diarize: bool = False
    admit: bool = False
    imported_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    schema_version: int = SESSION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> CaptureSession:
        return CaptureSession(
            session_id=str(data.get("session_id") or ""),
            state=str(data.get("state") or ""),
            title=str(data.get("title") or ""),
            device=str(data.get("device") or ""),
            mix_mic=str(data.get("mix_mic") or ""),
            started_at=str(data.get("started_at") or ""),
            stopped_at=(str(data["stopped_at"]) if data.get("stopped_at") else None),
            wav_path=str(data.get("wav_path") or ""),
            mp3_path=(str(data["mp3_path"]) if data.get("mp3_path") else None),
            json_path=(str(data["json_path"]) if data.get("json_path") else None),
            ffmpeg_pid=(int(data["ffmpeg_pid"]) if data.get("ffmpeg_pid") else None),
            diarize=bool(data.get("diarize")),
            admit=bool(data.get("admit")),
            imported_paths=[str(p) for p in (data.get("imported_paths") or [])],
            warnings=[str(w) for w in (data.get("warnings") or [])],
            errors=[str(e) for e in (data.get("errors") or [])],
            schema_version=int(data.get("schema_version") or SESSION_SCHEMA_VERSION),
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def new_session_id() -> str:
    return f"{utc_now()}-{uuid.uuid4().hex[:6]}"


def parse_avfoundation_devices(text: str) -> list[tuple[int, str]]:
    """Parse `ffmpeg -f avfoundation -list_devices` audio devices."""
    audio = False
    devices: list[tuple[int, str]] = []
    for line in text.splitlines():
        if _AUDIO_HEADER.search(line):
            audio = True
            continue
        if _VIDEO_HEADER.search(line):
            audio = False
            continue
        if not audio:
            continue
        match = _DEV_LINE.search(line)
        if match:
            devices.append((int(match.group(1)), match.group(2).strip()))
    return devices


def match_audio_device(
    devices: Sequence[tuple[int, str]],
    prefer: str | None,
    *,
    require_blackhole: bool = False,
) -> tuple[int, str] | None:
    needle = (prefer or "").strip().lower()
    if needle:
        for idx, name in devices:
            lowered = name.lower()
            if lowered == needle or needle in lowered:
                return idx, name
    if require_blackhole or not needle:
        for idx, name in devices:
            if "blackhole" in name.lower():
                return idx, name
    return None


def match_mic_device(
    devices: Sequence[tuple[int, str]], prefer: str | None
) -> tuple[int, str] | None:
    needle = (prefer or "").strip().lower()
    if needle:
        return match_audio_device(devices, prefer, require_blackhole=False)
    for idx, name in devices:
        lowered = name.lower()
        if "blackhole" in lowered:
            continue
        if "mic" in lowered or "microphone" in lowered:
            return idx, name
    return None


def build_record_cmd(
    ffmpeg: str | Path,
    device_name: str,
    wav_path: Path,
    *,
    mix_mic_name: str | None = None,
    max_duration_seconds: int | None = None,
) -> list[str]:
    cmd = [
        str(ffmpeg),
        "-nostdin",
        "-y",
        "-f",
        "avfoundation",
        "-i",
        f":{device_name}",
    ]
    if mix_mic_name:
        cmd.extend(
            [
                "-f",
                "avfoundation",
                "-i",
                f":{mix_mic_name}",
                "-filter_complex",
                "amix=inputs=2:duration=longest:dropout_transition=0",
            ]
        )
    if max_duration_seconds and max_duration_seconds > 0:
        cmd.extend(["-t", str(int(max_duration_seconds))])
    cmd.extend(["-ac", "1", "-ar", "48000", str(wav_path)])
    return cmd


def build_whispermlx_cmd(
    binary: Path,
    mp3_path: Path,
    output_dir: Path,
    *,
    model: str,
    language: str,
    diarize: bool,
) -> list[str]:
    """WhisperX-shaped JSON. Never put HF_TOKEN on argv."""
    cmd = [
        str(binary),
        str(mp3_path),
        "--output_dir",
        str(output_dir),
        "--language",
        language,
        "--model",
        model,
        "-f",
        "json",
    ]
    if diarize:
        cmd.append("--diarize")
    return cmd


def find_whispermlx(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    found = shutil.which("whispermlx")
    return Path(found) if found else None


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_ffmpeg(pid: int | None, *, timeout: float = 8.0) -> None:
    if not pid or not pid_alive(pid):
        return
    try:
        os.kill(pid, signal.SIGINT)
    except OSError:
        return
    deadline = time.time() + timeout
    while time.time() < deadline and pid_alive(pid):
        time.sleep(0.1)
    if not pid_alive(pid):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + 2.0
    while time.time() < deadline and pid_alive(pid):
        time.sleep(0.1)
    if pid_alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def spawn_ffmpeg(cmd: Sequence[str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("ab")
    proc = subprocess.Popen(
        list(cmd),
        stdout=handle,
        stderr=handle,
        start_new_session=True,
    )
    return int(proc.pid)


def session_path(sessions_dir: Path, session_id: str) -> Path:
    return sessions_dir / f"{session_id}.json"


def save_session(sessions_dir: Path, session: CaptureSession) -> Path:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    path = session_path(sessions_dir, session.session_id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(session.to_dict(), indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_session(path: Path) -> CaptureSession:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"session is not an object: {path}")
    return CaptureSession.from_dict(data)


def list_sessions(sessions_dir: Path) -> list[CaptureSession]:
    if not sessions_dir.is_dir():
        return []
    items: list[CaptureSession] = []
    for path in sorted(sessions_dir.glob("*.json")):
        if path.name.endswith(".tmp"):
            continue
        try:
            items.append(load_session(path))
        except (OSError, ValueError, json.JSONDecodeError, TypeError):
            continue
    return items


def find_active_session(sessions_dir: Path) -> CaptureSession | None:
    for session in list_sessions(sessions_dir):
        if session.state in RECORDING_STATES:
            return session
    return None


def latest_session(sessions_dir: Path) -> CaptureSession | None:
    items = list_sessions(sessions_dir)
    return items[-1] if items else None


def session_elapsed_seconds(session: CaptureSession) -> float | None:
    if not session.started_at:
        return None
    try:
        started = datetime.strptime(session.started_at, "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - started).total_seconds()


def reclaim_abandoned(
    sessions_dir: Path, *, max_duration_seconds: int | None = None
) -> list[CaptureSession]:
    reclaimed: list[CaptureSession] = []
    for session in list_sessions(sessions_dir):
        if session.state not in RECORDING_STATES:
            continue
        if pid_alive(session.ffmpeg_pid):
            continue
        elapsed = session_elapsed_seconds(session)
        hit_cap = (
            max_duration_seconds is not None
            and max_duration_seconds > 0
            and elapsed is not None
            and elapsed >= max_duration_seconds
        )
        session.stopped_at = session.stopped_at or utc_now()
        session.ffmpeg_pid = None
        if hit_cap:
            session.state = "recorded"
            warning = f"stopped at max_duration_seconds={max_duration_seconds}"
            if warning not in session.warnings:
                session.warnings.append(warning)
        else:
            session.state = "abandoned"
            session.errors.append("ffmpeg PID is dead; session marked abandoned")
        save_session(sessions_dir, session)
        reclaimed.append(session)
    return reclaimed


def wav_rms(path: Path, *, max_seconds: float = 2.0) -> float | None:
    try:
        with wave.open(str(path), "rb") as handle:
            frames_n = handle.getnframes()
            rate = handle.getframerate()
            if frames_n <= 0 or rate <= 0:
                return 0.0
            take = min(frames_n, int(rate * max_seconds))
            payload = handle.readframes(take)
            if not payload:
                return 0.0
            return float(audioop.rms(payload, handle.getsampwidth()))
    except (OSError, wave.Error, audioop.error):
        return None


def free_bytes(path: Path) -> int | None:
    try:
        probe = path if path.exists() else path.parent
        return int(shutil.disk_usage(probe).free)
    except OSError:
        return None


def _as_optional_path(value: Any) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return Path(text).expanduser()


def _parse_int(value: Any, default: int) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def portable_defaults() -> dict[str, Any]:
    recordings_root = _as_optional_path(os.environ.get("TRANSCRIPTX_RECORDINGS_DIR"))
    transcripts_root = _as_optional_path(os.environ.get("TRANSCRIPTX_TRANSCRIPTS_DIR"))
    data_dir = _as_optional_path(os.environ.get("TRANSCRIPTX_DATA_DIR"))
    env_file = ""
    repo = find_repo_root()
    if repo is not None and (repo / "whisperx.env").is_file():
        env_file = str(repo / "whisperx.env")
    transcripts = None
    if transcripts_root is not None:
        if transcripts_root.name == "originals":
            transcripts = transcripts_root
        else:
            transcripts = transcripts_root / "originals"
    return {
        "version": CONFIG_VERSION,
        "recordings": str(recordings_root / "capture") if recordings_root else "",
        "transcripts": str(transcripts) if transcripts else "",
        "sessions_dir": (str(data_dir / "capture" / "sessions") if data_dir else ""),
        "env_file": env_file,
        "whispermlx": "",
        "ffmpeg": "",
        "model": "",
        "language": "",
        "device": "",
        "mix_mic_device": "",
        "admit_python": "",
        "library_inbox": "",
        "watcher_inbox": "",
        "voice_note_inbox": "",
        "max_duration_seconds": 7200,
        "min_free_bytes": 524288000,
        "silent_input_seconds": 5,
        "silent_rms_threshold": 80,
    }


def env_derived_config() -> dict[str, Any]:
    prefix = "SYSTEM_AUDIO_CAPTURE_"
    mapping = {
        "recordings": "RECORDINGS",
        "transcripts": "TRANSCRIPTS",
        "sessions_dir": "SESSIONS_DIR",
        "env_file": "ENV_FILE",
        "whispermlx": "WHISPERMLX",
        "ffmpeg": "FFMPEG",
        "model": "MODEL",
        "language": "LANGUAGE",
        "device": "DEVICE",
        "mix_mic_device": "MIX_MIC_DEVICE",
        "admit_python": "ADMIT_PYTHON",
        "library_inbox": "LIBRARY_INBOX",
        "watcher_inbox": "WATCHER_INBOX",
        "voice_note_inbox": "VOICE_NOTE_INBOX",
        "max_duration_seconds": "MAX_DURATION_SECONDS",
        "min_free_bytes": "MIN_FREE_BYTES",
        "silent_input_seconds": "SILENT_INPUT_SECONDS",
        "silent_rms_threshold": "SILENT_RMS_THRESHOLD",
    }
    out: dict[str, Any] = {}
    for key, suffix in mapping.items():
        raw = os.environ.get(prefix + suffix)
        if raw is None or not str(raw).strip():
            continue
        out[key] = raw.strip()
    return out


def resolve_config_path(args: argparse.Namespace) -> Path:
    if getattr(args, "config", None):
        return Path(args.config).expanduser()
    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser()
    repo = find_repo_root()
    if repo is not None:
        return repo / ".transcriptx" / "system-audio-capture.json"
    return Path(".transcriptx/system-audio-capture.json")


def load_config_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: config {path} is not an object")
    unknown = [key for key in data if key not in KNOWN_CONFIG_KEYS]
    if unknown:
        raise SystemExit("ERROR: unknown config keys: " + ", ".join(sorted(unknown)))
    return data


def _cli_overrides(args: argparse.Namespace) -> dict[str, Any]:
    out: dict[str, Any] = {}
    mapping = {
        "recordings": "recordings",
        "transcripts": "transcripts",
        "sessions_dir": "sessions_dir",
        "env_file": "env_file",
        "whispermlx": "whispermlx",
        "ffmpeg": "ffmpeg",
        "model": "model",
        "language": "language",
        "device": "device",
        "mix_mic_device": "mix_mic_device",
        "admit_python": "admit_python",
        "library_inbox": "library_inbox",
        "watcher_inbox": "watcher_inbox",
        "voice_note_inbox": "voice_note_inbox",
        "max_duration_seconds": "max_duration_seconds",
        "min_free_bytes": "min_free_bytes",
    }
    for field_name, attr in mapping.items():
        if not hasattr(args, attr):
            continue
        value = getattr(args, attr)
        if value is None or value == "":
            continue
        out[field_name] = value
    return out


def dict_to_config(data: dict[str, Any]) -> EffectiveConfig:
    paths = {key: _as_optional_path(data.get(key)) for key in _PATH_KEYS}
    return EffectiveConfig(
        recordings=paths["recordings"],
        transcripts=paths["transcripts"],
        sessions_dir=paths["sessions_dir"],
        env_file=paths["env_file"],
        whispermlx=paths["whispermlx"],
        ffmpeg=paths["ffmpeg"],
        admit_python=paths["admit_python"],
        library_inbox=paths["library_inbox"],
        watcher_inbox=paths["watcher_inbox"],
        voice_note_inbox=paths["voice_note_inbox"],
        model=str(data.get("model") or "").strip(),
        language=str(data.get("language") or "").strip(),
        device=str(data.get("device") or "").strip(),
        mix_mic_device=str(data.get("mix_mic_device") or "").strip(),
        max_duration_seconds=_parse_int(data.get("max_duration_seconds"), 7200),
        min_free_bytes=_parse_int(data.get("min_free_bytes"), 524288000),
        silent_input_seconds=_parse_int(data.get("silent_input_seconds"), 5),
        silent_rms_threshold=_parse_int(data.get("silent_rms_threshold"), 80),
    )


def resolve_config(args: argparse.Namespace) -> EffectiveConfig:
    merged = portable_defaults()
    merged.update(env_derived_config())
    config_path = resolve_config_path(args)
    merged.update(load_config_file(config_path))
    merged.update(_cli_overrides(args))
    return dict_to_config(merged)


def config_to_dict(cfg: EffectiveConfig) -> dict[str, Any]:
    def _p(value: Path | None) -> str:
        return str(value) if value is not None else ""

    return {
        "version": CONFIG_VERSION,
        "recordings": _p(cfg.recordings),
        "transcripts": _p(cfg.transcripts),
        "sessions_dir": _p(cfg.sessions_dir),
        "env_file": _p(cfg.env_file),
        "whispermlx": _p(cfg.whispermlx),
        "ffmpeg": _p(cfg.ffmpeg),
        "model": cfg.model,
        "language": cfg.language,
        "device": cfg.device,
        "mix_mic_device": cfg.mix_mic_device,
        "admit_python": _p(cfg.admit_python),
        "library_inbox": _p(cfg.library_inbox),
        "watcher_inbox": _p(cfg.watcher_inbox),
        "voice_note_inbox": _p(cfg.voice_note_inbox),
        "max_duration_seconds": cfg.max_duration_seconds,
        "min_free_bytes": cfg.min_free_bytes,
        "silent_input_seconds": cfg.silent_input_seconds,
        "silent_rms_threshold": cfg.silent_rms_threshold,
    }


def validate_layout(cfg: EffectiveConfig) -> str | None:
    if cfg.recordings is None:
        return "recordings is required (WAV destination, typically recordings/capture)."
    if cfg.sessions_dir is None:
        return "sessions_dir is required (typically data_dir/capture/sessions)."
    if cfg.transcripts is not None and iw.looks_like_managed_library_root(
        cfg.transcripts
    ):
        return (
            "transcripts must be the originals/ folder "
            "(e.g. …/transcripts/originals), not the managed library root."
        )
    recordings = cfg.recordings
    forbidden: list[tuple[str, Path | None]] = [
        ("library inbox-watch inbox", cfg.library_inbox),
        ("G2 watcher inbox", cfg.watcher_inbox),
        ("G4 voice-note inbox", cfg.voice_note_inbox),
    ]
    for label, other in forbidden:
        if other is None:
            continue
        if iw.is_same_or_under(recordings, other) or iw.is_same_or_under(
            other, recordings
        ):
            return (
                f"recordings must not be {label} ({other}). "
                "G5 owns recordings/capture; do not share G2/G4/inbox-watch folders."
            )
    if cfg.max_duration_seconds <= 0:
        return (
            "max_duration_seconds must be a positive integer (refuse, do not truncate)."
        )
    if cfg.min_free_bytes < 0:
        return "min_free_bytes must be >= 0."
    return None


def resolve_model_language(cfg: EffectiveConfig) -> tuple[str, str]:
    model = cfg.model
    language = cfg.language
    if model and language:
        return model, language
    repo = find_repo_root()
    data: dict[str, Any] = {}
    if repo is not None:
        sibling = repo / ".transcriptx" / "whispermlx-missing.json"
        if sibling.is_file():
            try:
                loaded = json.loads(sibling.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = {}
            if isinstance(loaded, dict):
                data = loaded
    model = model or str(data.get("model") or "").strip() or "large-v3"
    language = language or str(data.get("language") or "").strip() or "en"
    return model, language


def _proc_env(env_file: Path | None) -> dict[str, str]:
    proc_env = os.environ.copy()
    if env_file is not None and env_file.is_file():
        proc_env.update(iw.parse_env_file(env_file))
    return proc_env


def probe_ffmpeg_devices(ffmpeg: Path) -> tuple[list[tuple[int, str]], str]:
    try:
        proc = subprocess.run(
            [str(ffmpeg), "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return [], str(exc)
    text = (proc.stderr or "") + "\n" + (proc.stdout or "")
    return parse_avfoundation_devices(text), text


def _need_sessions(cfg: EffectiveConfig) -> Path:
    if cfg.sessions_dir is None:
        raise SystemExit("ERROR: sessions_dir is required.")
    return cfg.sessions_dir


def cmd_probe(cfg: EffectiveConfig, *, as_json: bool = False) -> int:
    err = require_darwin()
    if err:
        _log(err, err=True)
        return 2
    ffmpeg = iw.find_ffmpeg(cfg.ffmpeg)
    if ffmpeg is None:
        _log(
            "ERROR: ffmpeg not found (set ffmpeg / SYSTEM_AUDIO_CAPTURE_FFMPEG).",
            err=True,
        )
        return 2
    devices, raw = probe_ffmpeg_devices(ffmpeg)
    hole = match_audio_device(devices, cfg.device or None, require_blackhole=True)
    mic = match_mic_device(devices, cfg.mix_mic_device or None)
    payload = {
        "ffmpeg": str(ffmpeg),
        "devices": [{"index": i, "name": n} for i, n in devices],
        "blackhole": ({"index": hole[0], "name": hole[1]} if hole else None),
        "mic": {"index": mic[0], "name": mic[1]} if mic else None,
        "recipe": (
            "Install BlackHole 2ch, create a Multi-Output Device "
            "(Built-in Output + BlackHole) in Audio MIDI Setup, and set that "
            "as system output so you still hear audio while this script captures."
        ),
    }
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0 if hole else 1
    _log(f"ffmpeg: {ffmpeg}")
    if not devices:
        _log("No AVFoundation audio devices parsed.")
        _log(raw.strip() or "(empty ffmpeg output)")
    for idx, name in devices:
        _log(f"  [{idx}] {name}")
    if hole:
        _log(f"BlackHole match: [{hole[0]}] {hole[1]}")
    else:
        _log("No BlackHole device. " + payload["recipe"], err=True)
        return 1
    if mic:
        _log(f"Mic match (optional --mix-mic): [{mic[0]}] {mic[1]}")
    return 0


def _prepare_start(
    cfg: EffectiveConfig,
    *,
    title: str,
    mix_mic: bool,
    dry_run: bool,
) -> tuple[CaptureSession, list[str]] | int:
    err = require_darwin()
    if err:
        _log(err, err=True)
        return 2
    layout = validate_layout(cfg)
    if layout:
        _log("ERROR: " + layout, err=True)
        return 2
    sessions_dir = _need_sessions(cfg)
    reclaim_abandoned(sessions_dir, max_duration_seconds=cfg.max_duration_seconds)
    active = find_active_session(sessions_dir)
    if active is not None:
        _log(
            f"ERROR: session {active.session_id} is already {active.state}. "
            "Stop or finalize it first.",
            err=True,
        )
        return 2
    recordings = cfg.recordings
    assert recordings is not None
    free = free_bytes(recordings)
    if free is not None and free < cfg.min_free_bytes:
        _log(
            f"ERROR: free disk {free} bytes is below min_free_bytes "
            f"{cfg.min_free_bytes}. Refuse rather than record.",
            err=True,
        )
        return 2
    ffmpeg = iw.find_ffmpeg(cfg.ffmpeg)
    if ffmpeg is None:
        _log("ERROR: ffmpeg not found.", err=True)
        return 2
    devices, _raw = probe_ffmpeg_devices(ffmpeg)
    hole = match_audio_device(devices, cfg.device or None, require_blackhole=True)
    if hole is None and allow_non_darwin() and cfg.device:
        hole = (0, cfg.device)
    if hole is None:
        _log(
            "ERROR: no BlackHole device. Install BlackHole 2ch and a "
            "Multi-Output Device so system audio reaches capture while you hear it.",
            err=True,
        )
        return 2
    mix_name = ""
    if mix_mic:
        mic = match_mic_device(devices, cfg.mix_mic_device or None)
        if mic is None and allow_non_darwin() and cfg.mix_mic_device:
            mic = (1, cfg.mix_mic_device)
        if mic is None:
            _log(
                "ERROR: --mix-mic requested but no microphone device matched. "
                "Create an Aggregate Device in Audio MIDI Setup, or pass "
                "--mix-mic-device.",
                err=True,
            )
            return 2
        mix_name = mic[1]
    session_id = new_session_id()
    wav_path = recordings / f"{session_id}.wav"
    cmd = build_record_cmd(
        ffmpeg,
        hole[1],
        wav_path,
        mix_mic_name=mix_name or None,
        max_duration_seconds=cfg.max_duration_seconds,
    )
    session = CaptureSession(
        session_id=session_id,
        state="recording",
        title=title or session_id,
        device=hole[1],
        mix_mic=mix_name,
        started_at=utc_now(),
        wav_path=str(wav_path),
    )
    if dry_run:
        _log("dry-run record: " + " ".join(cmd))
        return session, cmd
    recordings.mkdir(parents=True, exist_ok=True)
    log_path = sessions_dir / f"{session_id}.ffmpeg.log"
    session.ffmpeg_pid = spawn_ffmpeg(cmd, log_path)
    save_session(sessions_dir, session)
    _log(f"recording {session.session_id} pid={session.ffmpeg_pid} -> {wav_path}")
    return session, cmd


def cmd_start(
    cfg: EffectiveConfig,
    *,
    title: str = "",
    mix_mic: bool = False,
    dry_run: bool = False,
) -> int:
    result = _prepare_start(cfg, title=title, mix_mic=mix_mic, dry_run=dry_run)
    if isinstance(result, int):
        return result
    return 0


def cmd_status(cfg: EffectiveConfig, *, as_json: bool = False) -> int:
    sessions_dir = _need_sessions(cfg)
    reclaim_abandoned(sessions_dir, max_duration_seconds=cfg.max_duration_seconds)
    session = find_active_session(sessions_dir) or latest_session(sessions_dir)
    if session is None:
        payload = {"session": None}
        if as_json:
            print(json.dumps(payload))
        else:
            _log("No capture sessions.")
        return 0
    if as_json:
        print(json.dumps(session.to_dict(), indent=2))
    else:
        _log(f"{session.session_id}  {session.state}  {session.title}")
        if session.device:
            _log(f"  device: {session.device}")
        if session.mix_mic:
            _log(f"  mix-mic: {session.mix_mic}")
        if session.wav_path:
            _log(f"  wav: {session.wav_path}")
        if session.json_path:
            _log(f"  json: {session.json_path}")
        for warning in session.warnings:
            _log(f"  warning: {warning}")
        for error in session.errors:
            _log(f"  error: {error}")
    return 0


def cmd_list(cfg: EffectiveConfig) -> int:
    sessions_dir = _need_sessions(cfg)
    reclaim_abandoned(sessions_dir, max_duration_seconds=cfg.max_duration_seconds)
    items = list_sessions(sessions_dir)
    if not items:
        _log("No capture sessions.")
        return 0
    for session in items:
        _log(f"{session.session_id}  {session.state}  {session.title}")
    return 0


def maybe_warn_silent(cfg: EffectiveConfig, session: CaptureSession) -> None:
    wav = Path(session.wav_path)
    if not wav.is_file():
        return
    rms = wav_rms(wav)
    if rms is None:
        return
    if rms <= cfg.silent_rms_threshold:
        warning = (
            f"near-silent WAV (rms={rms:.1f} <= {cfg.silent_rms_threshold}). "
            "Multi-Output Device is probably not routing into BlackHole."
        )
        if warning not in session.warnings:
            session.warnings.append(warning)
            _log("WARNING: " + warning, err=True)


def convert_wav(cfg: EffectiveConfig, wav: Path) -> Path | None:
    ffmpeg = iw.find_ffmpeg(cfg.ffmpeg)
    if ffmpeg is None:
        _log("ERROR: ffmpeg not found for convert.", err=True)
        return None
    dest = wav.with_suffix(".mp3")
    partial = dest.with_name(dest.name + ".partial")
    cmd = iw.build_ffmpeg_cmd(ffmpeg, wav, partial)
    result = iw.run_ffmpeg(cmd)
    if result.returncode != 0 or not partial.is_file():
        _log("ERROR: ffmpeg convert failed.", err=True)
        if partial.exists():
            partial.unlink()
        return None
    os.replace(partial, dest)
    return dest


def _discover_json(output_dir: Path, stem: str) -> Path | None:
    exact = output_dir / f"{stem}.json"
    if exact.is_file():
        return exact
    candidates = [p for p in output_dir.glob("*.json") if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def transcribe_json(
    cfg: EffectiveConfig,
    mp3: Path,
    *,
    diarize: bool,
    dry_run: bool,
) -> Path | None:
    if cfg.transcripts is None:
        _log("ERROR: transcripts (originals/) is required to transcribe.", err=True)
        return None
    if iw.looks_like_managed_library_root(cfg.transcripts):
        _log("ERROR: transcripts must be originals/, not the library root.", err=True)
        return None
    dest = cfg.transcripts / f"{mp3.stem}.json"
    if dest.is_file():
        _log(f"skip transcribe; {dest.name} already exists")
        return dest
    binary = find_whispermlx(cfg.whispermlx)
    if binary is None:
        _log("ERROR: whispermlx not found (set WHISPERMLX / --whispermlx).", err=True)
        return None
    model, language = resolve_model_language(cfg)
    temp_dir = cfg.transcripts / TEMP_DIR_NAME / mp3.stem
    cmd = build_whispermlx_cmd(
        binary, mp3, temp_dir, model=model, language=language, diarize=diarize
    )
    if dry_run:
        _log("dry-run transcribe: " + " ".join(cmd))
        return dest
    temp_dir.mkdir(parents=True, exist_ok=True)
    cfg.transcripts.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(cmd, check=False, env=_proc_env(cfg.env_file))
    if result.returncode != 0:
        _log(f"ERROR: whispermlx exited {result.returncode}.", err=True)
        return None
    found = _discover_json(temp_dir, mp3.stem)
    if found is None:
        _log("ERROR: whispermlx wrote no JSON.", err=True)
        return None
    if dest.exists():
        _log(f"skip transcribe; {dest.name} already exists")
        return dest
    shutil.copy2(found, dest)
    return dest


def maybe_admit(cfg: EffectiveConfig, *, dry_run: bool) -> tuple[int, list[str]]:
    if cfg.transcripts is None:
        return 1, []
    python = iw.find_admit_python(cfg.admit_python)
    if python is None:
        _log("ERROR: no Python that can import transcriptx.admit_originals.", err=True)
        return 1, []
    cmd = iw.build_admit_cmd(python, transcripts=cfg.transcripts, dry_run=dry_run)
    if dry_run:
        _log("dry-run admit: " + " ".join(cmd))
        return 0, []
    code = iw.run_admit_originals(cmd)
    return code, []


def finalize_session(
    cfg: EffectiveConfig,
    session: CaptureSession,
    *,
    transcribe: bool,
    admit: bool,
    diarize: bool,
    dry_run: bool,
) -> int:
    sessions_dir = _need_sessions(cfg)
    session.diarize = diarize
    session.admit = admit
    wav = Path(session.wav_path)
    maybe_warn_silent(cfg, session)
    if session.state in RECORDING_STATES:
        stop_ffmpeg(session.ffmpeg_pid)
        session.ffmpeg_pid = None
        session.stopped_at = utc_now()
        session.state = "recorded"
        save_session(sessions_dir, session)
    if not transcribe:
        save_session(sessions_dir, session)
        _log(f"{session.session_id} recorded (no transcribe)")
        return 0
    if not wav.is_file():
        session.state = "failed"
        session.errors.append(f"WAV missing: {wav}")
        save_session(sessions_dir, session)
        _log("ERROR: WAV missing after stop.", err=True)
        return 1
    session.state = "transcribing"
    save_session(sessions_dir, session)
    mp3 = convert_wav(cfg, wav)
    if mp3 is None:
        session.state = "failed"
        session.errors.append("ffmpeg convert failed")
        save_session(sessions_dir, session)
        return 1
    session.mp3_path = str(mp3)
    json_path = transcribe_json(cfg, mp3, diarize=diarize, dry_run=dry_run)
    if json_path is None:
        session.state = "failed"
        session.errors.append("whispermlx JSON missing")
        save_session(sessions_dir, session)
        return 1
    session.json_path = str(json_path)
    session.state = "transcribed"
    save_session(sessions_dir, session)
    if not admit:
        _log(f"{session.session_id} transcribed -> {json_path}")
        return 0
    session.state = "admitting"
    save_session(sessions_dir, session)
    code, imported = maybe_admit(cfg, dry_run=dry_run)
    if code != 0:
        session.state = "failed"
        session.errors.append("admit_originals failed")
        save_session(sessions_dir, session)
        return 1
    session.imported_paths = imported
    session.state = "admitted"
    save_session(sessions_dir, session)
    _log(f"{session.session_id} admitted")
    return 0


def _resolve_target(
    cfg: EffectiveConfig, session_id: str | None
) -> CaptureSession | None:
    sessions_dir = _need_sessions(cfg)
    reclaim_abandoned(sessions_dir, max_duration_seconds=cfg.max_duration_seconds)
    if session_id:
        path = session_path(sessions_dir, session_id)
        if not path.is_file():
            _log(f"ERROR: no session {session_id}", err=True)
            return None
        return load_session(path)
    active = find_active_session(sessions_dir)
    if active is not None:
        return active
    latest = latest_session(sessions_dir)
    if latest is None:
        _log("ERROR: no capture session to stop/finalize.", err=True)
    return latest


def cmd_stop(
    cfg: EffectiveConfig,
    *,
    session_id: str | None = None,
    transcribe: bool = True,
    admit: bool = False,
    diarize: bool = False,
    dry_run: bool = False,
) -> int:
    session = _resolve_target(cfg, session_id)
    if session is None:
        return 2
    return finalize_session(
        cfg,
        session,
        transcribe=transcribe,
        admit=admit,
        diarize=diarize,
        dry_run=dry_run,
    )


def cmd_finalize(
    cfg: EffectiveConfig,
    session_id: str | None,
    *,
    admit: bool,
    diarize: bool,
    dry_run: bool,
) -> int:
    session = _resolve_target(cfg, session_id)
    if session is None:
        return 2
    if session.state in RECORDING_STATES and pid_alive(session.ffmpeg_pid):
        _log(
            "ERROR: session is still recording; use stop, not finalize.",
            err=True,
        )
        return 2
    if session.state in RECORDING_STATES:
        session.state = "abandoned"
        session.stopped_at = session.stopped_at or utc_now()
        save_session(_need_sessions(cfg), session)
    return finalize_session(
        cfg,
        session,
        transcribe=True,
        admit=admit,
        diarize=diarize,
        dry_run=dry_run,
    )


def cmd_record(
    cfg: EffectiveConfig,
    *,
    title: str,
    mix_mic: bool,
    transcribe: bool,
    admit: bool,
    diarize: bool,
    dry_run: bool,
) -> int:
    result = _prepare_start(cfg, title=title, mix_mic=mix_mic, dry_run=dry_run)
    if isinstance(result, int):
        return result
    session, _cmd = result
    if dry_run:
        return 0
    sessions_dir = _need_sessions(cfg)
    started = time.time()
    warned = False
    try:
        while pid_alive(session.ffmpeg_pid):
            elapsed = time.time() - started
            if not warned and elapsed >= cfg.silent_input_seconds:
                maybe_warn_silent(cfg, session)
                save_session(sessions_dir, session)
                warned = True
            if elapsed >= cfg.max_duration_seconds:
                session.warnings.append(
                    f"stopped at max_duration_seconds={cfg.max_duration_seconds}"
                )
                _log("duration cap reached; stopping", err=True)
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        _log("interrupt; stopping")
    return finalize_session(
        cfg,
        session,
        transcribe=transcribe,
        admit=admit,
        diarize=diarize,
        dry_run=False,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mac BlackHole system-audio capture (roadmap G5)."
    )
    parser.add_argument("--config")
    parser.add_argument("--recordings")
    parser.add_argument("--transcripts")
    parser.add_argument("--sessions-dir", dest="sessions_dir")
    parser.add_argument("--env-file", dest="env_file")
    parser.add_argument("--whispermlx")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--model")
    parser.add_argument("--language")
    parser.add_argument("--device")
    parser.add_argument("--mix-mic-device", dest="mix_mic_device")
    parser.add_argument("--admit-python", dest="admit_python")
    parser.add_argument("--library-inbox", dest="library_inbox")
    parser.add_argument("--watcher-inbox", dest="watcher_inbox")
    parser.add_argument("--voice-note-inbox", dest="voice_note_inbox")
    parser.add_argument("--max-duration-seconds", dest="max_duration_seconds", type=int)
    parser.add_argument("--min-free-bytes", dest="min_free_bytes", type=int)
    parser.add_argument("--show-config", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")

    sub = parser.add_subparsers(dest="command")
    probe_p = sub.add_parser(
        "probe", help="List AVFoundation devices and match BlackHole"
    )
    probe_p.add_argument("--json", action="store_true", dest="as_json")
    start_p = sub.add_parser("start", help="Start a background capture session")
    start_p.add_argument("--name", default="", help="Session title")
    start_p.add_argument(
        "--mix-mic",
        action="store_true",
        help="Mix a microphone with system audio (headphones meetings)",
    )
    status_p = sub.add_parser("status", help="Show active or latest session")
    status_p.add_argument("--json", action="store_true", dest="as_json")
    sub.add_parser("list", help="List sessions")
    stop_p = sub.add_parser("stop", help="Stop capture and optionally transcribe")
    stop_p.add_argument("session_id", nargs="?")
    stop_p.add_argument("--no-transcribe", action="store_true")
    stop_p.add_argument("--admit", action="store_true")
    stop_p.add_argument("--diarize", action="store_true")
    rec_p = sub.add_parser("record", help="Foreground capture until Ctrl-C")
    rec_p.add_argument("--name", default="")
    rec_p.add_argument("--mix-mic", action="store_true")
    rec_p.add_argument("--no-transcribe", action="store_true")
    rec_p.add_argument("--admit", action="store_true")
    rec_p.add_argument("--diarize", action="store_true")
    fin_p = sub.add_parser("finalize", help="Recover a leftover WAV (crash)")
    fin_p.add_argument("session_id", nargs="?")
    fin_p.add_argument("--admit", action="store_true")
    fin_p.add_argument("--diarize", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = resolve_config(args)
    if args.show_config:
        print(json.dumps(config_to_dict(cfg), indent=2))
        return 0
    command = args.command or "status"
    dry_run = bool(args.dry_run)
    if command == "probe":
        return cmd_probe(cfg, as_json=bool(args.as_json))
    if command == "start":
        return cmd_start(
            cfg,
            title=str(getattr(args, "name", "") or ""),
            mix_mic=bool(getattr(args, "mix_mic", False)),
            dry_run=dry_run,
        )
    if command == "status":
        return cmd_status(cfg, as_json=bool(args.as_json))
    if command == "list":
        return cmd_list(cfg)
    if command == "stop":
        return cmd_stop(
            cfg,
            session_id=getattr(args, "session_id", None),
            transcribe=not bool(getattr(args, "no_transcribe", False)),
            admit=bool(getattr(args, "admit", False)),
            diarize=bool(getattr(args, "diarize", False)),
            dry_run=dry_run,
        )
    if command == "record":
        return cmd_record(
            cfg,
            title=str(getattr(args, "name", "") or ""),
            mix_mic=bool(getattr(args, "mix_mic", False)),
            transcribe=not bool(getattr(args, "no_transcribe", False)),
            admit=bool(getattr(args, "admit", False)),
            diarize=bool(getattr(args, "diarize", False)),
            dry_run=dry_run,
        )
    if command == "finalize":
        return cmd_finalize(
            cfg,
            getattr(args, "session_id", None),
            admit=bool(getattr(args, "admit", False)),
            diarize=bool(getattr(args, "diarize", False)),
            dry_run=dry_run,
        )
    _log(f"ERROR: unknown command {command}", err=True)
    return 2


if __name__ == "__main__":
    sys.exit(main())
