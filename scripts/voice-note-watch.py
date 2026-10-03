#!/usr/bin/env python3
"""
Host-side voice-note watcher — short recording to plain text, then stop.

Sibling of inbox-watch / whispermlx-missing. Not a Streamlit page and not
the in-app directory watcher. Streamlit never executes it. It does not
load the transcriptx package. There is no library admission and no speaker auto-name.

Own inbox, not the live library inbox (on the owner machine,
/Volumes/USB-DISK/RECORD). inbox-watch is not recursive, so a subdirectory
such as RECORD/braindump is invisible to the library watcher only when the
recorder can write that folder. If the device only writes the library inbox
root, this script refuses to share it.

Pipeline: removable volume → local stage → ffmpeg (same 16 kHz mono 64k MP3
as inbox-watch) → whispermlx -f txt, never --diarize. Output is plain text
under notes_dir, not diarized JSON under originals/. Audio stays on the
machine, in a private audio_dir (not the library recordings folder).

A length cap (max_duration_seconds, required) refuses an oversized file.
The source is not truncated and not deleted. When library_inbox is set it
must be the inbox-watch inbox; the untouched source is copied there once.

Optional --triage writes a local draft (todos, questions, unverified claims).
No mail, no git, no other app. Default off. Do not start this from the login
agent that runs inbox-watch --watch.

Install:
    install -m 755 scripts/voice-note-watch.py ~/.local/bin/voice-note-watch

Config (merge order: portable defaults <- env <- local JSON <- CLI):
    --config /path/to/config.json
    or env VOICE_NOTE_WATCH_CONFIG
    default: .transcriptx/voice-note-watch.json when run from the repo

    Example: config/voice-note-watch.example.json
    max_duration_seconds in that example (180) is an operator starting point,
    not the 20-minute voice-note merge gap.

Exit 0 = all ok (refusals are not failures); 1 = one or more item failures;
2 = CLI/config/validation error.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence

CONFIG_VERSION = 1
CONFIG_PATH: Path | None = None
CONFIG_ENV_VAR = "VOICE_NOTE_WATCH_CONFIG"
STATE_NAME = "voice-note-watch-state.json"
TEMP_DIR_NAME = ".whispermlx-voice-note"

ConfigSource = Literal["cli", "json", "env", "portable", "unset"]

_DURATION_RE = re.compile(
    r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)"
)
_TODO_RE = re.compile(
    r"\b(todo|remind me|need to|don't forget|don’t forget|do not forget)\b",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

KNOWN_CONFIG_KEYS = frozenset(
    {
        "version",
        "inbox",
        "audio_dir",
        "notes_dir",
        "max_duration_seconds",
        "library_watch_config",
        "library_inbox",
        "env_file",
        "whispermlx",
        "ffmpeg",
        "model",
        "language",
        "triage",
        "interval_seconds",
        "stage_local",
        "stage_dir",
        "recursive",
    }
)

_PATH_KEYS = (
    "inbox",
    "audio_dir",
    "notes_dir",
    "library_watch_config",
    "library_inbox",
    "env_file",
    "whispermlx",
    "ffmpeg",
    "stage_dir",
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


def _print_section(title: str) -> None:
    _log("---")
    _log(title)
    _log("---")


@dataclass
class ConfigProvenance:
    inbox: ConfigSource = "unset"
    audio_dir: ConfigSource = "unset"
    notes_dir: ConfigSource = "unset"
    library_watch_config: ConfigSource = "unset"
    library_inbox: ConfigSource = "unset"
    env_file: ConfigSource = "unset"
    whispermlx: ConfigSource = "unset"
    ffmpeg: ConfigSource = "unset"
    stage_dir: ConfigSource = "unset"


@dataclass
class EffectiveConfig:
    inbox: Path | None
    audio_dir: Path | None
    notes_dir: Path | None
    max_duration_seconds: float | None
    library_watch_config: Path | None
    library_inbox: Path | None
    env_file: Path | None
    whispermlx: Path | None
    ffmpeg: Path | None
    model: str | None
    language: str | None
    triage: bool
    interval_seconds: float
    stage_local: bool | None
    stage_dir: Path | None
    recursive: bool
    provenance: ConfigProvenance = field(default_factory=ConfigProvenance)


@dataclass
class SiblingLayout:
    path: Path
    inbox: Path
    recordings: Path
    transcripts: Path
    recursive: bool


@dataclass
class CycleStats:
    transcribed: int = 0
    skipped: int = 0
    refused: int = 0
    failed: int = 0
    would_transcribe: int = 0
    would_copy: int = 0
    overflow_copied: int = 0
    drafted: int = 0
    unstable: int = 0


def find_repo_root() -> Path | None:
    script_dir = Path(__file__).resolve().parent
    if script_dir.name != "scripts":
        return None
    return script_dir.parent


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Watch a voice-note inbox: stage, convert, transcribe to plain text. "
            "Does not admit into the library."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            "Config JSON path (default: .transcriptx/voice-note-watch.json). "
            f"Override with {CONFIG_ENV_VAR}."
        ),
    )
    parser.add_argument("--inbox", type=Path, default=None)
    parser.add_argument("--audio-dir", dest="audio_dir", type=Path, default=None)
    parser.add_argument("--notes-dir", dest="notes_dir", type=Path, default=None)
    parser.add_argument(
        "--max-duration-seconds",
        dest="max_duration_seconds",
        type=float,
        default=None,
        help="Refuse longer files. Required. Do not truncate.",
    )
    parser.add_argument(
        "--library-watch-config",
        dest="library_watch_config",
        type=Path,
        default=None,
        help="inbox-watch JSON used to prove this inbox is not the library inbox.",
    )
    parser.add_argument(
        "--library-inbox",
        dest="library_inbox",
        type=Path,
        default=None,
        help=(
            "Copy oversized sources here once. Must be the inbox-watch inbox. "
            "Source is left in place."
        ),
    )
    parser.add_argument("--env-file", dest="env_file", type=Path, default=None)
    parser.add_argument("--whispermlx", type=Path, default=None)
    parser.add_argument("--ffmpeg", type=Path, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--language", default=None)
    parser.add_argument("--stage-dir", dest="stage_dir", type=Path, default=None)
    parser.add_argument(
        "--interval",
        dest="interval_seconds",
        type=float,
        default=None,
        help="Poll interval in seconds when --watch (default: 5).",
    )

    stage_group = parser.add_mutually_exclusive_group()
    stage_group.add_argument(
        "--stage-local",
        dest="stage_local",
        action="store_true",
        default=None,
        help="Always copy inbox audio locally before ffmpeg.",
    )
    stage_group.add_argument(
        "--no-stage-local",
        dest="stage_local",
        action="store_false",
        help="Never stage; ffmpeg reads the inbox path.",
    )

    triage_group = parser.add_mutually_exclusive_group()
    triage_group.add_argument(
        "--triage",
        dest="triage",
        action="store_true",
        default=None,
        help="Write a local draft next to the text. Default off.",
    )
    triage_group.add_argument(
        "--no-triage",
        dest="triage",
        action="store_false",
        help="Do not write a draft (default).",
    )

    run_group = parser.add_mutually_exclusive_group()
    run_group.add_argument("--once", action="store_true", help="Single scan (default).")
    run_group.add_argument(
        "--watch",
        dest="watch_loop",
        action="store_true",
        help="Poll until interrupted. Not the inbox-watch login agent.",
    )

    rec_group = parser.add_mutually_exclusive_group()
    rec_group.add_argument("--recursive", action="store_true", default=None)
    rec_group.add_argument("--no-recursive", dest="recursive", action="store_false")

    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing note or draft.",
    )
    parser.add_argument("--show-config", action="store_true")
    parser.add_argument("--save-config", action="store_true")
    parser.add_argument(
        "--stability-checks",
        dest="stability_checks",
        type=int,
        default=3,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--stability-interval-ms",
        dest="stability_interval_ms",
        type=int,
        default=500,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--stability-timeout-ms",
        dest="stability_timeout_ms",
        type=int,
        default=30_000,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def resolve_config_path(args: argparse.Namespace) -> Path:
    if args.config is not None:
        return args.config.expanduser()
    env_val = os.environ.get(CONFIG_ENV_VAR, "").strip()
    if env_val:
        return Path(env_val).expanduser()
    if CONFIG_PATH is not None:
        return CONFIG_PATH
    repo_root = find_repo_root()
    if repo_root is not None:
        return repo_root / ".transcriptx" / "voice-note-watch.json"
    return Path.cwd() / ".voice-note-watch-no-config.json"


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"ERROR: invalid config file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: config file must be a JSON object: {path}")
    return data


def load_config(path: Path) -> dict[str, Any]:
    data = _load_json_object(path)
    for key in data:
        if key not in KNOWN_CONFIG_KEYS:
            print(f"WARNING: ignoring unknown config key: {key}", file=sys.stderr)
    return data


def _parse_bool_env(value: str | None, *, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in ("true", "1", "yes", "on"):
        return True
    if normalized in ("false", "0", "no", "off"):
        return False
    return default


def require_bool(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("true", "1", "yes", "on"):
            return True
        if normalized in ("false", "0", "no", "off"):
            return False
    raise SystemExit(f"ERROR: config key {key!r} must be a boolean, got {value!r}")


def _as_optional_path(value: Any) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        text = str(value).strip()
    else:
        text = str(value).strip()
    if not text:
        return None
    return Path(text).expanduser()


def _apply_voice_env(repo_root: Path | None) -> None:
    if repo_root is None:
        return
    for key, value in iw.parse_env_file(repo_root / ".env").items():
        if key.startswith("VOICE_NOTE_WATCH_"):
            os.environ.setdefault(key, value)


def portable_defaults(repo_root: Path | None) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "triage": False,
        "recursive": False,
        "interval_seconds": 5,
        "stage_local": None,
    }
    if repo_root is None:
        return defaults
    defaults["library_watch_config"] = str(
        repo_root / ".transcriptx" / "inbox-watch.json"
    )
    env_file = repo_root / "whisperx.env"
    if env_file.is_file():
        defaults["env_file"] = str(env_file)
    return defaults


def env_derived_config() -> dict[str, Any]:
    derived: dict[str, Any] = {}
    mapping = {
        "VOICE_NOTE_WATCH_INBOX": "inbox",
        "VOICE_NOTE_WATCH_AUDIO_DIR": "audio_dir",
        "VOICE_NOTE_WATCH_NOTES_DIR": "notes_dir",
        "VOICE_NOTE_WATCH_LIBRARY_WATCH_CONFIG": "library_watch_config",
        "VOICE_NOTE_WATCH_LIBRARY_INBOX": "library_inbox",
        "VOICE_NOTE_WATCH_ENV_FILE": "env_file",
        "VOICE_NOTE_WATCH_WHISPERMLX": "whispermlx",
        "VOICE_NOTE_WATCH_FFMPEG": "ffmpeg",
        "VOICE_NOTE_WATCH_STAGE_DIR": "stage_dir",
        "VOICE_NOTE_WATCH_MODEL": "model",
        "VOICE_NOTE_WATCH_LANGUAGE": "language",
    }
    for env_key, key in mapping.items():
        raw = os.environ.get(env_key, "").strip()
        if raw:
            derived[key] = raw
    duration = os.environ.get("VOICE_NOTE_WATCH_MAX_DURATION_SECONDS", "").strip()
    if duration:
        derived["max_duration_seconds"] = duration
    if os.environ.get("VOICE_NOTE_WATCH_TRIAGE", "").strip():
        derived["triage"] = _parse_bool_env(
            os.environ.get("VOICE_NOTE_WATCH_TRIAGE"), default=False
        )
    if os.environ.get("VOICE_NOTE_WATCH_RECURSIVE", "").strip():
        derived["recursive"] = _parse_bool_env(
            os.environ.get("VOICE_NOTE_WATCH_RECURSIVE"), default=False
        )
    interval = os.environ.get("VOICE_NOTE_WATCH_INTERVAL", "").strip()
    if interval:
        derived["interval_seconds"] = interval
    stage = os.environ.get("VOICE_NOTE_WATCH_STAGE_LOCAL", "").strip()
    if stage:
        derived["stage_local"] = _parse_bool_env(stage, default=False)
    return derived


def _parse_duration(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(
            f"ERROR: max_duration_seconds must be a positive number, got {value!r}"
        ) from exc
    if number <= 0:
        raise SystemExit(
            f"ERROR: max_duration_seconds must be positive, got {value!r}"
        )
    return number


def resolve_config(
    args: argparse.Namespace, *, config_path: Path
) -> EffectiveConfig:
    repo_root = find_repo_root()
    _apply_voice_env(repo_root)
    merged: dict[str, Any] = {}
    merged.update(portable_defaults(repo_root))
    merged.update(env_derived_config())
    merged.update(load_config(config_path))

    cli_paths = {
        "inbox": args.inbox,
        "audio_dir": args.audio_dir,
        "notes_dir": args.notes_dir,
        "library_watch_config": args.library_watch_config,
        "library_inbox": args.library_inbox,
        "env_file": args.env_file,
        "whispermlx": args.whispermlx,
        "ffmpeg": args.ffmpeg,
        "stage_dir": args.stage_dir,
    }
    for key, value in cli_paths.items():
        if value is not None:
            merged[key] = str(value)
    if args.max_duration_seconds is not None:
        merged["max_duration_seconds"] = args.max_duration_seconds
    if args.model is not None:
        merged["model"] = args.model
    if args.language is not None:
        merged["language"] = args.language
    if args.triage is not None:
        merged["triage"] = args.triage
    if args.recursive is not None:
        merged["recursive"] = args.recursive
    if args.interval_seconds is not None:
        merged["interval_seconds"] = args.interval_seconds
    if args.stage_local is not None:
        merged["stage_local"] = args.stage_local

    interval_raw = merged.get("interval_seconds", 5)
    try:
        interval = float(interval_raw)
    except (TypeError, ValueError) as exc:
        raise SystemExit(
            f"ERROR: interval_seconds must be a number, got {interval_raw!r}"
        ) from exc

    stage_local = merged.get("stage_local", None)
    if stage_local is not None and not isinstance(stage_local, bool):
        stage_local = require_bool(stage_local, "stage_local")

    return EffectiveConfig(
        inbox=_as_optional_path(merged.get("inbox")),
        audio_dir=_as_optional_path(merged.get("audio_dir")),
        notes_dir=_as_optional_path(merged.get("notes_dir")),
        max_duration_seconds=_parse_duration(merged.get("max_duration_seconds")),
        library_watch_config=_as_optional_path(merged.get("library_watch_config")),
        library_inbox=_as_optional_path(merged.get("library_inbox")),
        env_file=_as_optional_path(merged.get("env_file")),
        whispermlx=_as_optional_path(merged.get("whispermlx")),
        ffmpeg=_as_optional_path(merged.get("ffmpeg")),
        model=(str(merged["model"]).strip() or None) if merged.get("model") else None,
        language=(str(merged["language"]).strip() or None)
        if merged.get("language")
        else None,
        triage=require_bool(merged.get("triage", False), "triage"),
        interval_seconds=interval,
        stage_local=stage_local if isinstance(stage_local, bool) or stage_local is None else None,
        stage_dir=_as_optional_path(merged.get("stage_dir")),
        recursive=require_bool(merged.get("recursive", False), "recursive"),
    )


def config_to_dict(cfg: EffectiveConfig) -> dict[str, Any]:
    def _s(path: Path | None) -> str | None:
        return str(path) if path is not None else None

    return {
        "version": CONFIG_VERSION,
        "inbox": _s(cfg.inbox),
        "audio_dir": _s(cfg.audio_dir),
        "notes_dir": _s(cfg.notes_dir),
        "max_duration_seconds": cfg.max_duration_seconds,
        "library_watch_config": _s(cfg.library_watch_config),
        "library_inbox": _s(cfg.library_inbox),
        "env_file": _s(cfg.env_file),
        "whispermlx": _s(cfg.whispermlx),
        "ffmpeg": _s(cfg.ffmpeg),
        "model": cfg.model,
        "language": cfg.language,
        "triage": cfg.triage,
        "interval_seconds": cfg.interval_seconds,
        "stage_local": cfg.stage_local,
        "stage_dir": _s(cfg.stage_dir),
        "recursive": cfg.recursive,
    }


def _anchor(path: Path, repo_root: Path | None) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    base = repo_root if repo_root is not None else Path.cwd()
    return base / expanded


def load_sibling(path: Path) -> tuple[SiblingLayout | None, str | None]:
    if not path.is_file():
        return None, (
            "library watch config is missing; cannot prove this inbox is not "
            f"the library inbox: {path}"
        )
    try:
        data = _load_json_object(path)
    except SystemExit as exc:
        return None, str(exc)
    inbox = _as_optional_path(data.get("inbox"))
    recordings = _as_optional_path(data.get("recordings"))
    transcripts = _as_optional_path(data.get("transcripts"))
    if inbox is None:
        return None, f"library watch config has no inbox: {path}"
    if recordings is None:
        return None, (
            "library watch config has no recordings; cannot prove audio_dir "
            f"is private: {path}"
        )
    if transcripts is None:
        return None, (
            "library watch config has no transcripts; cannot prove notes_dir "
            f"is outside originals/: {path}"
        )
    recursive = data.get("recursive", False)
    if not isinstance(recursive, bool):
        try:
            recursive = require_bool(recursive, "recursive")
        except SystemExit as exc:
            return None, str(exc)
    return (
        SiblingLayout(
            path=path,
            inbox=inbox,
            recordings=recordings,
            transcripts=transcripts,
            recursive=recursive,
        ),
        None,
    )


def _same(path: Path, other: Path) -> bool:
    try:
        return path.expanduser().resolve() == other.expanduser().resolve()
    except OSError:
        return False


def _under(path: Path, root: Path) -> bool:
    return iw.is_same_or_under(path, root)


def _strict_under(path: Path, root: Path) -> bool:
    return _under(path, root) and not _same(path, root)


def validate_layout(
    cfg: EffectiveConfig, sibling: SiblingLayout
) -> str | None:
    if cfg.inbox is None:
        return "inbox is required."
    if cfg.audio_dir is None:
        return "audio_dir is required."
    if cfg.notes_dir is None:
        return "notes_dir is required."
    if cfg.max_duration_seconds is None:
        return (
            "max_duration_seconds is required "
            "(set it in config or --max-duration-seconds; there is no default)."
        )
    if cfg.library_watch_config is None:
        return "library_watch_config is required."

    inbox = cfg.inbox
    if _same(inbox, sibling.inbox):
        return (
            "voice-note inbox must not be the library inbox "
            f"({sibling.inbox}). Use a different folder. "
            "If the recorder can only write that root, do not share it."
        )
    if _strict_under(sibling.inbox, inbox):
        return (
            "voice-note inbox must not contain the library inbox "
            f"({sibling.inbox})."
        )
    if _strict_under(inbox, sibling.inbox) and sibling.recursive:
        return (
            "library inbox-watch is recursive, so this subdirectory is visible "
            f"to it ({inbox}). Do not share that tree."
        )

    library_root = iw.transcripts_root_for_admit(sibling.transcripts)
    forbidden = [
        ("the voice-note inbox", inbox),
        ("the library inbox", sibling.inbox),
        ("library recordings", sibling.recordings),
        ("library transcripts", sibling.transcripts),
        ("the managed library root", library_root),
    ]
    for label, dest in (("audio_dir", cfg.audio_dir), ("notes_dir", cfg.notes_dir)):
        for name, root in forbidden:
            if _under(dest, root):
                return f"{label} must not be {name} or a path under it ({root})."
    if _same(cfg.audio_dir, cfg.notes_dir):
        return "audio_dir and notes_dir must be different folders."
    if iw.looks_like_managed_library_root(cfg.notes_dir):
        return (
            "notes_dir must not be the managed library root "
            "(the folder that contains metadata/, originals/, or imports/)."
        )
    if cfg.library_inbox is not None:
        if not _same(cfg.library_inbox, sibling.inbox):
            return (
                "library_inbox must be the inbox-watch inbox "
                f"({sibling.inbox}), not {cfg.library_inbox}."
            )
        if _same(cfg.library_inbox, inbox):
            return "library_inbox must not be the voice-note inbox."
    stage_dir = cfg.stage_dir
    if stage_dir is not None and (
        _same(stage_dir, inbox) or _under(inbox, stage_dir) or _under(stage_dir, inbox)
    ):
        return "stage_dir must not be the inbox or a path under it."
    if stage_dir is not None and _same(stage_dir, cfg.audio_dir):
        return "stage_dir must not be audio_dir (use a subdirectory)."
    return None


def resolve_model_language(cfg: EffectiveConfig) -> tuple[str, str]:
    model = cfg.model
    language = cfg.language
    if model and language:
        return model, language
    repo_root = find_repo_root()
    sibling_path = None
    if repo_root is not None:
        sibling_path = repo_root / ".transcriptx" / "whispermlx-missing.json"
    data: dict[str, Any] = {}
    if sibling_path is not None and sibling_path.is_file():
        try:
            loaded = _load_json_object(sibling_path)
        except SystemExit:
            loaded = {}
        if isinstance(loaded, dict):
            data = loaded
    # Never inherit diarize or output_format from the library STT config.
    model = model or str(data.get("model") or "").strip() or "large-v3"
    language = language or str(data.get("language") or "").strip() or "en"
    return model, language


def want_stage(cfg: EffectiveConfig, inbox: Path) -> bool:
    if cfg.stage_local is True:
        return True
    if cfg.stage_local is False:
        return False
    return bool(iw.inbox_on_removable_volume(inbox))


def effective_stage_dir(cfg: EffectiveConfig) -> Path | None:
    if cfg.stage_dir is not None:
        return cfg.stage_dir
    if cfg.audio_dir is not None:
        return cfg.audio_dir / iw.STAGE_DIR_NAME
    return None


def probe_duration_seconds(ffmpeg: Path, src: Path) -> float | None:
    try:
        proc = subprocess.run(
            [str(ffmpeg), "-nostdin", "-i", str(src)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    text = (proc.stderr or "") + "\n" + (proc.stdout or "")
    match = _DURATION_RE.search(text)
    if match is None:
        return None
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = float(match.group(3))
    return hours * 3600 + minutes * 60 + seconds


def whispermlx_txt_supported(help_text: str) -> bool:
    has_flag = "output_format" in help_text or re.search(r"(^|\s)-f\b", help_text)
    if not has_flag:
        return False
    return re.search(r"\btxt\b", help_text) is not None


def probe_whispermlx_txt(whispermlx: Path) -> bool:
    try:
        proc = subprocess.run(
            [str(whispermlx), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    help_text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return whispermlx_txt_supported(help_text)


def build_whispermlx_cmd(
    binary: Path,
    mp3_path: Path,
    temp_dir: Path,
    *,
    model: str,
    language: str,
) -> list[str]:
    """Plain text only. Never diarize and never put a token on argv."""
    return [
        str(binary),
        str(mp3_path),
        "--output_dir",
        str(temp_dir),
        "--language",
        language,
        "--model",
        model,
        "-f",
        "txt",
    ]


def find_whispermlx(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    found = shutil.which("whispermlx")
    return Path(found) if found else None


def _proc_env(env_file: Path | None) -> dict[str, str]:
    proc_env = os.environ.copy()
    if env_file is not None and env_file.is_file():
        proc_env.update(iw.parse_env_file(env_file))
    return proc_env


def _file_stamp(path: Path) -> tuple[int, int] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
    return int(st.st_size), mtime_ns


def load_state(path: Path) -> dict[str, Any]:
    empty: dict[str, Any] = {"version": 1, "overflow": {}}
    if not path.is_file():
        return empty
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _log(f"WARNING: ignoring unreadable state file: {path}", err=True)
        return empty
    if not isinstance(data, dict):
        return empty
    overflow = data.get("overflow")
    if not isinstance(overflow, dict):
        overflow = {}
    return {"version": 1, "overflow": overflow}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "overflow": state.get("overflow") or {}}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _state_key(src: Path) -> str:
    try:
        return str(src.resolve())
    except OSError:
        return str(src)


def copy_overflow(
    src: Path,
    library_inbox: Path,
    *,
    state_path: Path,
    dry_run: bool,
) -> str:
    """Copy src into the library inbox once. Never move or delete src."""
    stamp = _file_stamp(src)
    if stamp is None:
        return "failed"
    dest = library_inbox / src.name
    key = _state_key(src)
    state = load_state(state_path)
    overflow: dict[str, Any] = state["overflow"]
    previous = overflow.get(key)
    if (
        isinstance(previous, dict)
        and previous.get("size") == stamp[0]
        and previous.get("mtime_ns") == stamp[1]
    ):
        _log(f"  Overflow already handed off: {src.name}")
        return "already"

    if dry_run:
        _log(f"  Would copy to library inbox: {src.name} -> {dest}")
        return "dry_run"

    if not library_inbox.is_dir():
        _log(
            f"ERROR: library inbox is not a directory, left source in place: "
            f"{library_inbox}",
            err=True,
        )
        return "failed"
    if dest.exists():
        _log(f"  Library inbox already has {dest.name}; left source in place.")
        overflow[key] = {
            "size": stamp[0],
            "mtime_ns": stamp[1],
            "copied_to": str(dest),
            "skipped_existing": True,
        }
        save_state(state_path, state)
        return "exists"

    try:
        shutil.copy2(src, dest)
    except OSError as exc:
        _log(f"ERROR: overflow copy failed for {src.name}: {exc}", err=True)
        return "failed"
    overflow[key] = {
        "size": stamp[0],
        "mtime_ns": stamp[1],
        "copied_to": str(dest),
    }
    save_state(state_path, state)
    _log(f"  Copied to library inbox: {src.name} -> {dest} (source kept)")
    return "copied"


def build_draft(text: str) -> str:
    """Deterministic draft. Claims stay unverified. No network and no mail."""
    todos: list[str] = []
    questions: list[str] = []
    claims: list[str] = []
    pieces = [part.strip() for part in _SENTENCE_RE.split(text) if part.strip()]
    if not pieces and text.strip():
        pieces = [text.strip()]
    for sentence in pieces:
        if _TODO_RE.search(sentence):
            todos.append(sentence)
        elif sentence.endswith("?"):
            questions.append(sentence)
        else:
            claims.append(sentence)

    def _section(title: str, rows: list[str], *, claim: bool) -> str:
        if not rows:
            body = "(none)"
        elif claim:
            body = "\n".join(f"- unverified: {row}" for row in rows)
        else:
            body = "\n".join(f"- {row}" for row in rows)
        return f"## {title}\n\n{body}"

    header = (
        "# Voice note draft\n\n"
        "Draft only. Not admitted to the library. Claims are unverified."
    )
    body = "\n\n".join(
        [
            header,
            _section("Todos", todos, claim=False),
            _section("Questions", questions, claim=False),
            _section("Claims", claims, claim=True),
        ]
    )
    return body + "\n"


def write_draft(txt_path: Path, *, force: bool, dry_run: bool) -> str:
    draft_path = txt_path.with_suffix(".draft.md")
    if draft_path.exists() and not force:
        _log(f"  Draft exists: {draft_path.name}")
        return "skipped"
    if dry_run:
        _log(f"  Would write draft: {draft_path.name}")
        return "dry_run"
    try:
        text = txt_path.read_text(encoding="utf-8")
    except OSError as exc:
        _log(f"ERROR: cannot read {txt_path.name} for triage: {exc}", err=True)
        return "failed"
    draft_path.write_text(build_draft(text), encoding="utf-8")
    _log(f"  Draft: {draft_path.name}")
    return "written"


def _discover_txt(temp_dir: Path, stem: str) -> Path | None:
    exact = temp_dir / f"{stem}.txt"
    if exact.is_file():
        return exact
    matches = [
        path
        for path in temp_dir.rglob("*.txt")
        if path.is_file() and not path.name.startswith(".")
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def convert_to_mp3(
    src: Path,
    audio_dir: Path,
    *,
    ffmpeg: Path,
    display: Path,
    dry_run: bool,
) -> str:
    dest = audio_dir / f"{display.stem}.mp3"
    partial = audio_dir / f".voice-note-watch.{display.stem}.mp3.partial"
    if dry_run:
        cmd = iw.build_ffmpeg_cmd(ffmpeg, src, dest)
        _log(f"  Would convert: {' '.join(cmd)}")
        return "dry_run"
    audio_dir.mkdir(parents=True, exist_ok=True)
    cmd = iw.build_ffmpeg_cmd(ffmpeg, src, partial)
    _log(f"  Converting: {display.name} -> {dest.name}")
    result = iw.run_ffmpeg(cmd)
    if result.returncode != 0:
        partial.unlink(missing_ok=True)
        _log(
            f"ERROR: ffmpeg failed for {display.name} (exit {result.returncode})",
            err=True,
        )
        return "failed"
    os.replace(partial, dest)
    _log(f"  Converted: {display.name} -> {dest.name}")
    return "converted"


def transcribe_txt(
    mp3_path: Path,
    notes_dir: Path,
    *,
    whispermlx: Path,
    model: str,
    language: str,
    env_file: Path | None,
    force: bool,
    dry_run: bool,
) -> str:
    stem = mp3_path.stem
    target = notes_dir / f"{stem}.txt"
    temp_dir = notes_dir / TEMP_DIR_NAME / stem
    cmd = build_whispermlx_cmd(
        whispermlx, mp3_path, temp_dir, model=model, language=language
    )
    if dry_run:
        _log(f"  Would transcribe: {' '.join(cmd)}")
        return "dry_run"
    if target.exists() and not force:
        _log(f"  Skipping (text exists): {target.name}")
        return "skipped"
    notes_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    _log(f"  Transcribing: {mp3_path.name} -> {target.name}")
    try:
        proc = subprocess.run(
            cmd,
            env=_proc_env(env_file),
            check=False,
        )
    except OSError as exc:
        _log(f"ERROR: whispermlx failed to start for {mp3_path.name}: {exc}", err=True)
        return "failed"
    if proc.returncode != 0:
        _log(
            f"ERROR: whispermlx exit {proc.returncode} for {mp3_path.name} "
            f"(temp left at {temp_dir})",
            err=True,
        )
        return "failed"
    candidate = _discover_txt(temp_dir, stem)
    if candidate is None:
        _log(
            f"ERROR: no plain text from whispermlx for {mp3_path.name}; "
            f"JSON was not promoted (temp left at {temp_dir})",
            err=True,
        )
        return "failed"
    notes_dir.mkdir(parents=True, exist_ok=True)
    os.replace(candidate, target)
    try:
        shutil.rmtree(temp_dir)
    except OSError:
        pass
    _log(f"  Wrote: {target.name}")
    return "transcribed"


def _refuse_message(
    src: Path,
    *,
    reason: str,
    sibling: SiblingLayout,
    cfg: EffectiveConfig,
) -> None:
    extra = " Not truncated."
    if reason == "over":
        if cfg.library_inbox is None and _strict_under(cfg.inbox or src, sibling.inbox):
            extra += (
                " This inbox is not scanned by non-recursive inbox-watch;"
                " set library_inbox to hand the file to the library watcher."
            )
        else:
            extra += " Left for the library watcher."
    elif reason == "unknown":
        extra += " Left in place."
    label = "over max_duration_seconds" if reason == "over" else "duration unknown"
    _log(f"  Refused ({label}): {src.name}.{extra}")


def process_cycle(
    cfg: EffectiveConfig,
    sibling: SiblingLayout,
    *,
    dry_run: bool,
    force: bool,
    ffmpeg: Path | None,
    whispermlx: Path | None,
    state_path: Path,
    stability_checks: int,
    stability_interval_ms: int,
    stability_timeout_ms: int,
) -> tuple[CycleStats, str | None]:
    assert cfg.inbox is not None
    assert cfg.audio_dir is not None
    assert cfg.notes_dir is not None
    assert cfg.max_duration_seconds is not None
    stats = CycleStats()
    model, language = resolve_model_language(cfg)
    stage = want_stage(cfg, cfg.inbox)
    stage_dir = effective_stage_dir(cfg)
    files = iw.discover_inbox_files(cfg.inbox, recursive=cfg.recursive)
    work = [path for path in files if iw.classify_path(path) == "audio"]

    _print_section("Review before cycle")
    _log(f"  Mode:       {'dry-run' if dry_run else 'run'}")
    _log(f"  Inbox:      {cfg.inbox}")
    _log(f"  Audio dir:  {cfg.audio_dir}")
    _log(f"  Notes dir:  {cfg.notes_dir}")
    _log(f"  Cap:        {cfg.max_duration_seconds:g}s")
    _log(f"  Triage:     {'on' if cfg.triage else 'off'}")
    _log(f"  Candidates: {len(work)}")
    if stage:
        _log("  Staging:    on")

    if not work:
        _log("No inbox audio this cycle.")
        return stats, None

    txt_ready: bool | None = None
    _print_section("Processing")
    total = len(work)
    for index, src in enumerate(work, start=1):
        _log(f"[{index}/{total}] audio: {src.name}")
        target_txt = cfg.notes_dir / f"{src.stem}.txt"
        if target_txt.is_file() and not force:
            _log(f"  Skipping (text exists): {target_txt.name}")
            stats.skipped += 1
            if cfg.triage:
                draft_outcome = write_draft(target_txt, force=force, dry_run=dry_run)
                if draft_outcome == "written":
                    stats.drafted += 1
            continue
        if not iw.wait_until_stable(
            src,
            checks=stability_checks,
            interval_ms=stability_interval_ms,
            timeout_ms=stability_timeout_ms,
        ):
            _log(f"  Unstable (skipped this cycle): {src.name}", err=True)
            stats.unstable += 1
            continue
        if ffmpeg is None:
            return stats, "ffmpeg not found (set --ffmpeg or PATH)."
        duration = probe_duration_seconds(ffmpeg, src)
        if duration is None or duration > cfg.max_duration_seconds:
            reason = "unknown" if duration is None else "over"
            _refuse_message(src, reason=reason, sibling=sibling, cfg=cfg)
            stats.refused += 1
            if reason == "over" and cfg.library_inbox is not None:
                copied = copy_overflow(
                    src,
                    cfg.library_inbox,
                    state_path=state_path,
                    dry_run=dry_run,
                )
                if copied == "copied":
                    stats.overflow_copied += 1
                elif copied == "dry_run":
                    stats.would_copy += 1
                elif copied == "failed":
                    stats.failed += 1
            continue

        if txt_ready is None:
            if whispermlx is None:
                return stats, "whispermlx not found (set --whispermlx or PATH)."
            if dry_run:
                txt_ready = True
            else:
                txt_ready = probe_whispermlx_txt(whispermlx)
                if not txt_ready:
                    return stats, (
                        "whispermlx does not advertise plain-text output (-f txt). "
                        "Refusing to fall back to JSON."
                    )

        convert_src = src
        if stage and stage_dir is not None:
            staged_path, stage_outcome = iw.stage_inbox_audio(
                src,
                stage_dir,
                force=force,
                dry_run=dry_run,
            )
            if stage_outcome == "failed":
                stats.failed += 1
                continue
            if staged_path is not None:
                convert_src = staged_path

        converted = convert_to_mp3(
            convert_src,
            cfg.audio_dir,
            ffmpeg=ffmpeg,
            display=src,
            dry_run=dry_run,
        )
        if converted == "failed":
            stats.failed += 1
            continue
        if converted == "dry_run":
            assert whispermlx is not None
            transcribe_txt(
                cfg.audio_dir / f"{src.stem}.mp3",
                cfg.notes_dir,
                whispermlx=whispermlx,
                model=model,
                language=language,
                env_file=cfg.env_file,
                force=force,
                dry_run=True,
            )
            stats.would_transcribe += 1
            if cfg.triage:
                _log(f"  Would write draft: {src.stem}.draft.md")
            continue

        assert whispermlx is not None
        outcome = transcribe_txt(
            cfg.audio_dir / f"{src.stem}.mp3",
            cfg.notes_dir,
            whispermlx=whispermlx,
            model=model,
            language=language,
            env_file=cfg.env_file,
            force=force,
            dry_run=False,
        )
        if outcome == "failed":
            stats.failed += 1
            continue
        if outcome == "skipped":
            stats.skipped += 1
        else:
            stats.transcribed += 1
        if cfg.triage and (cfg.notes_dir / f"{src.stem}.txt").is_file():
            draft_outcome = write_draft(
                cfg.notes_dir / f"{src.stem}.txt",
                force=force,
                dry_run=False,
            )
            if draft_outcome == "written":
                stats.drafted += 1
            elif draft_outcome == "failed":
                stats.failed += 1

    return stats, None


def print_summary(stats: CycleStats, *, dry_run: bool) -> None:
    if stats.failed:
        status = "failed" if stats.transcribed == 0 and not dry_run else "partial"
    elif dry_run:
        status = "dry-run"
    else:
        status = "completed"
    _print_section("Run summary")
    _log(f"  Status:     {status}")
    if dry_run:
        _log(f"  Would transcribe: {stats.would_transcribe}")
        _log(f"  Would copy:       {stats.would_copy}")
    else:
        _log(f"  Transcribed: {stats.transcribed}")
        _log(f"  Refused:     {stats.refused}")
        _log(f"  Skipped:     {stats.skipped}")
        _log(f"  Drafts:      {stats.drafted}")
        if stats.overflow_copied:
            _log(f"  Overflow:    {stats.overflow_copied}")
    if stats.failed:
        _log(f"  Failed:      {stats.failed}")
    _log("---")


def _missing_paths_message(cfg: EffectiveConfig) -> str | None:
    missing = []
    if cfg.inbox is None:
        missing.append("inbox")
    if cfg.audio_dir is None:
        missing.append("audio_dir")
    if cfg.notes_dir is None:
        missing.append("notes_dir")
    if cfg.max_duration_seconds is None:
        missing.append("max_duration_seconds")
    if cfg.library_watch_config is None:
        missing.append("library_watch_config")
    if not missing:
        return None
    return (
        "Missing required settings: "
        + ", ".join(missing)
        + ". Set them via CLI, .transcriptx/voice-note-watch.json, "
        "or VOICE_NOTE_WATCH_* env. There is no duration default."
    )


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(line_buffering=True)
            except (OSError, ValueError):
                pass
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 2

    config_path = resolve_config_path(args)
    try:
        cfg = resolve_config(args, config_path=config_path)
    except SystemExit as exc:
        message = exc.code if isinstance(exc.code, str) else exc
        print(f"ERROR: {message}", file=sys.stderr)
        return 2

    if args.show_config:
        print(json.dumps(config_to_dict(cfg), indent=2))
        return 0
    if args.save_config:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(config_to_dict(cfg), indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Saved config: {config_path}")

    missing = _missing_paths_message(cfg)
    if missing:
        print(f"ERROR: {missing}", file=sys.stderr)
        return 2

    assert cfg.library_watch_config is not None
    sibling_path = _anchor(cfg.library_watch_config, find_repo_root())
    sibling, sibling_error = load_sibling(sibling_path)
    if sibling_error or sibling is None:
        print(f"ERROR: {sibling_error}", file=sys.stderr)
        return 2
    layout_error = validate_layout(cfg, sibling)
    if layout_error:
        print(f"ERROR: {layout_error}", file=sys.stderr)
        return 2

    assert cfg.inbox is not None
    watch_loop = bool(args.watch_loop)
    if not args.dry_run and not cfg.inbox.is_dir():
        if watch_loop:
            _log(f"Waiting for inbox: {cfg.inbox}")
        else:
            print(f"ERROR: inbox is not a directory: {cfg.inbox}", file=sys.stderr)
            return 2

    ffmpeg = iw.find_ffmpeg(cfg.ffmpeg)
    whispermlx = find_whispermlx(cfg.whispermlx)
    if ffmpeg is None and not args.dry_run:
        # Duration probes need ffmpeg only when a cycle sees audio. Checked there.
        ffmpeg = None
    if ffmpeg is None and args.dry_run:
        ffmpeg = cfg.ffmpeg or Path("ffmpeg")
    if whispermlx is None and args.dry_run:
        whispermlx = cfg.whispermlx or Path("whispermlx")

    state_path = config_path.parent / STATE_NAME
    total_failed = 0
    inbox_absent_logged = not cfg.inbox.is_dir()
    try:
        while True:
            if watch_loop and not args.dry_run:
                if cfg.inbox.is_dir():
                    if inbox_absent_logged:
                        _log(f"Inbox is available: {cfg.inbox}")
                        inbox_absent_logged = False
                else:
                    if not inbox_absent_logged:
                        _log(f"Waiting for inbox: {cfg.inbox}")
                        inbox_absent_logged = True
                    time.sleep(max(cfg.interval_seconds, 0.1))
                    continue
            stats, fatal = process_cycle(
                cfg,
                sibling,
                dry_run=args.dry_run,
                force=args.force,
                ffmpeg=ffmpeg,
                whispermlx=whispermlx,
                state_path=state_path,
                stability_checks=args.stability_checks,
                stability_interval_ms=args.stability_interval_ms,
                stability_timeout_ms=args.stability_timeout_ms,
            )
            print_summary(stats, dry_run=args.dry_run)
            if fatal:
                print(f"ERROR: {fatal}", file=sys.stderr)
                return 2
            total_failed += stats.failed
            if not watch_loop:
                break
            time.sleep(max(cfg.interval_seconds, 0.1))
    except KeyboardInterrupt:
        _log()
        _log("Stopped.")
        return 0 if total_failed == 0 else 1
    return 1 if total_failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
