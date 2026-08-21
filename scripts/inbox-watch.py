#!/usr/bin/env python3
"""
Host-side inbox watcher — convert new audio and/or copy new transcripts.

This is a companion to whispermlx-missing, not the in-app G2 directory watcher.
Streamlit never executes it. It does not import transcriptx and does not admit
files into the managed library (use Import Transcript or Settings → Watcher).

The transcripts destination must be ``…/transcripts/originals`` (or another
non-library folder). Config that points at the managed library root (the
directory that already contains ``metadata/`` / ``imports/``) is rejected.

Install:
    install -m 755 scripts/inbox-watch.py ~/.local/bin/inbox-watch
    (ensure ~/.local/bin is on PATH)

Modes (independent; at least one required):
    --watch-audio         Convert new inbox audio → recordings as 16 kHz mono 64k MP3,
                          then run whispermlx-missing
    --watch-transcripts   Copy new inbox JSON/SRT/VTT/txt/html into transcripts dest
                          when that stem is not already present

Preview:
    inbox-watch --once --dry-run --inbox … --recordings … --transcripts …

Normal once (cron / launchd):
    inbox-watch --once

Poll:
    inbox-watch --watch

Config (merge order: portable defaults <- env <- local JSON <- CLI):
    --config /path/to/config.json
    or env INBOX_WATCH_CONFIG=/path/to/config.json
    default: .transcriptx/inbox-watch.json when run from the repo

    TRANSCRIPTX_RECORDINGS_DIR → recordings
    TRANSCRIPTX_TRANSCRIPTS_DIR → transcripts dest (script appends /originals)
    INBOX_WATCH_INBOX → inbox

Inbox files are kept by default. After a successful convert/copy you can
    --backup-wav (copy audio originals into the WAV backup folder),
    --delete-originals (remove the inbox source), both, or --move-processed DIR.

Exit 0 = all ok; 1 = one or more item failures; 2 = CLI/config/validation error.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence

CONFIG_VERSION = 1
CONFIG_PATH: Path | None = None
CONFIG_ENV_VAR = "INBOX_WATCH_CONFIG"

ConfigSource = Literal["cli", "json", "env", "portable", "unset"]
_MEANINGFUL_PATH_SOURCES = frozenset({"cli", "json", "env"})

Kind = Literal["audio", "transcript", "ignore"]

AUDIO_EXTENSIONS = frozenset(
    {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma"}
)
TRANSCRIPT_EXTENSIONS = frozenset(
    {".json", ".srt", ".vtt", ".txt", ".html", ".htm"}
)

KNOWN_CONFIG_KEYS = frozenset(
    {
        "version",
        "inbox",
        "recordings",
        "transcripts",
        "env_file",
        "whispermlx_missing",
        "ffmpeg",
        "watch_audio",
        "watch_transcripts",
        "recursive",
        "interval_seconds",
        "move_processed",
        "wav_backup",
        "backup_wavs",
        "delete_originals",
    }
)

_PATH_KEYS = (
    "inbox",
    "recordings",
    "transcripts",
    "env_file",
    "whispermlx_missing",
    "ffmpeg",
    "move_processed",
    "wav_backup",
)

FFMPEG_CHANNELS = "1"
FFMPEG_SAMPLE_RATE = "16000"
FFMPEG_CODEC = "libmp3lame"
FFMPEG_BITRATE = "64k"


@dataclass
class ConfigProvenance:
    inbox: ConfigSource = "unset"
    recordings: ConfigSource = "unset"
    transcripts: ConfigSource = "unset"
    env_file: ConfigSource = "unset"
    whispermlx_missing: ConfigSource = "unset"
    ffmpeg: ConfigSource = "unset"
    move_processed: ConfigSource = "unset"
    wav_backup: ConfigSource = "unset"


@dataclass
class EffectiveConfig:
    inbox: Path | None
    recordings: Path | None
    transcripts: Path | None
    env_file: Path | None
    whispermlx_missing: Path | None
    ffmpeg: Path | None
    watch_audio: bool
    watch_transcripts: bool
    recursive: bool
    interval_seconds: float
    move_processed: Path | None
    wav_backup: Path | None
    backup_wavs: bool
    delete_originals: bool
    provenance: ConfigProvenance = field(default_factory=ConfigProvenance)


@dataclass
class CycleStats:
    audio_converted: int = 0
    audio_skipped: int = 0
    audio_failed: int = 0
    transcripts_copied: int = 0
    transcripts_skipped: int = 0
    transcripts_failed: int = 0
    unstable: int = 0
    missing_invoked: int = 0
    originals_backed_up: int = 0
    originals_deleted: int = 0
    would_convert: int = 0
    would_copy: int = 0
    would_invoke_missing: int = 0
    would_backup: int = 0
    would_delete: int = 0
    converted_names: list[str] = field(default_factory=list)
    copied_names: list[str] = field(default_factory=list)
    failed_names: list[str] = field(default_factory=list)
    skipped_names: list[tuple[str, str]] = field(default_factory=list)
    unstable_names: list[str] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return self.audio_failed + self.transcripts_failed


def _log(msg: str = "", *, err: bool = False) -> None:
    print(msg, file=sys.stderr if err else sys.stdout, flush=True)


def _print_section(title: str) -> None:
    """Compact section banner — same shape as analysis Review / Run summary."""
    _log()
    _log("---")
    _log(title)
    _log("---")


def _print_limited_items(
    label: str, items: Sequence[str], *, limit: int = 12
) -> None:
    if not items:
        return
    shown = min(len(items), limit)
    _log(f"  {label}:")
    for item in items[:limit]:
        _log(f"    • {item}")
    if len(items) > limit:
        _log(f"    • ... and {len(items) - shown} more")


def _cycle_status(stats: CycleStats, *, dry_run: bool) -> str:
    if dry_run:
        return "dry-run"
    if stats.failed:
        if stats.audio_converted or stats.transcripts_copied:
            return "partial"
        return "failed"
    return "completed"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Watch an inbox for new audio (convert + whispermlx-missing) "
            "and/or new transcripts (copy if stem missing)."
        ),
    )
    parser.add_argument(
        "--config",
        dest="config",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Config JSON path (default: .transcriptx/inbox-watch.json in repo). "
            f"Override with {CONFIG_ENV_VAR}."
        ),
    )
    parser.add_argument("--inbox", type=Path, default=None)
    parser.add_argument("--recordings", type=Path, default=None)
    parser.add_argument("--transcripts", type=Path, default=None)
    parser.add_argument("--env-file", dest="env_file", type=Path, default=None)
    parser.add_argument(
        "--whispermlx-missing",
        dest="whispermlx_missing",
        type=Path,
        default=None,
        help="Path to whispermlx-missing (binary or scripts/whispermlx-missing.py).",
    )
    parser.add_argument("--ffmpeg", type=Path, default=None)
    parser.add_argument(
        "--move-processed",
        dest="move_processed",
        type=Path,
        default=None,
        help="After a successful convert/copy, move the inbox source here (never delete).",
    )
    parser.add_argument(
        "--wav-backup",
        dest="wav_backup",
        type=Path,
        default=None,
        help="WAV backup folder (default: TRANSCRIPTX_WAV_BACKUP_DIR / data/backups/wav).",
    )

    backup_group = parser.add_mutually_exclusive_group()
    backup_group.add_argument(
        "--backup-wav",
        dest="backup_wavs",
        action="store_true",
        default=None,
        help="After a successful audio convert, copy the inbox original into the WAV backup folder.",
    )
    backup_group.add_argument(
        "--no-backup-wav",
        dest="backup_wavs",
        action="store_false",
        help="Do not copy originals into the WAV backup folder (default).",
    )

    delete_group = parser.add_mutually_exclusive_group()
    delete_group.add_argument(
        "--delete-originals",
        dest="delete_originals",
        action="store_true",
        default=None,
        help="After a successful convert/copy (and backup, if enabled), delete the inbox source.",
    )
    delete_group.add_argument(
        "--no-delete-originals",
        dest="delete_originals",
        action="store_false",
        help="Keep inbox sources (default).",
    )

    audio_group = parser.add_mutually_exclusive_group()
    audio_group.add_argument(
        "--watch-audio",
        dest="watch_audio",
        action="store_true",
        default=None,
        help="Enable audio convert + whispermlx-missing (default: on if unset).",
    )
    audio_group.add_argument(
        "--no-watch-audio",
        dest="watch_audio",
        action="store_false",
        help="Disable audio handling.",
    )

    tx_group = parser.add_mutually_exclusive_group()
    tx_group.add_argument(
        "--watch-transcripts",
        dest="watch_transcripts",
        action="store_true",
        default=None,
        help="Enable transcript copy-if-new (default: on if unset).",
    )
    tx_group.add_argument(
        "--no-watch-transcripts",
        dest="watch_transcripts",
        action="store_false",
        help="Disable transcript handling.",
    )

    run_group = parser.add_mutually_exclusive_group()
    run_group.add_argument(
        "--once",
        action="store_true",
        help="Single scan (default). Suitable for cron/launchd.",
    )
    run_group.add_argument(
        "--watch",
        dest="watch_loop",
        action="store_true",
        help="Poll until interrupted.",
    )

    parser.add_argument(
        "--interval",
        dest="interval_seconds",
        type=float,
        default=None,
        help="Poll interval in seconds when --watch (default: 5).",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        default=None,
        help="Scan inbox subdirectories.",
    )
    parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Do not scan subdirectories (default).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned ffmpeg/copy/missing; do not write or invoke.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing destination stem.",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Print effective config and exit.",
    )
    parser.add_argument(
        "--save-config",
        action="store_true",
        help="Save resolved settings to the config file (see --config).",
    )
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
    parser.set_defaults(
        watch_audio=None,
        watch_transcripts=None,
        recursive=None,
        backup_wavs=None,
        delete_originals=None,
    )
    return parser.parse_args(argv)


def find_repo_root() -> Path | None:
    script_dir = Path(__file__).resolve().parent
    if script_dir.name != "scripts":
        return None
    return script_dir.parent


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            result[key] = value
    return result


def bootstrap_repo_env(repo_root: Path) -> None:
    dotenv_path = repo_root / ".env"
    for key, value in parse_env_file(dotenv_path).items():
        os.environ.setdefault(key, value)


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


def portable_defaults(repo_root: Path | None) -> tuple[dict[str, Any], ConfigProvenance]:
    provenance = ConfigProvenance()
    defaults: dict[str, Any] = {}
    if repo_root is None:
        return defaults, provenance
    defaults["inbox"] = str(repo_root / "data" / "transcript-inbox")
    provenance.inbox = "portable"
    defaults["recordings"] = str(repo_root / "data" / "recordings")
    provenance.recordings = "portable"
    defaults["transcripts"] = str(repo_root / "data" / "transcripts" / "originals")
    provenance.transcripts = "portable"
    defaults["env_file"] = str(repo_root / "whisperx.env")
    provenance.env_file = "portable"
    sibling = repo_root / "scripts" / "whispermlx-missing.py"
    if sibling.is_file():
        defaults["whispermlx_missing"] = str(sibling)
        provenance.whispermlx_missing = "portable"
    defaults["wav_backup"] = str(repo_root / "data" / "backups" / "wav")
    provenance.wav_backup = "portable"
    return defaults, provenance


def env_derived_config() -> tuple[dict[str, Any], ConfigProvenance]:
    provenance = ConfigProvenance()
    derived: dict[str, Any] = {}

    inbox = os.environ.get("INBOX_WATCH_INBOX", "").strip()
    if inbox:
        derived["inbox"] = inbox
        provenance.inbox = "env"

    recordings = os.environ.get("TRANSCRIPTX_RECORDINGS_DIR", "").strip()
    if recordings:
        derived["recordings"] = recordings
        provenance.recordings = "env"

    transcripts_base = os.environ.get("TRANSCRIPTX_TRANSCRIPTS_DIR", "").strip()
    if transcripts_base:
        derived["transcripts"] = str(Path(transcripts_base).expanduser() / "originals")
        provenance.transcripts = "env"

    env_file = os.environ.get("INBOX_WATCH_ENV_FILE", "").strip()
    if env_file:
        derived["env_file"] = env_file
        provenance.env_file = "env"

    missing = os.environ.get("INBOX_WATCH_WHISPERMLX_MISSING", "").strip()
    if missing:
        derived["whispermlx_missing"] = missing
        provenance.whispermlx_missing = "env"

    ffmpeg = os.environ.get("INBOX_WATCH_FFMPEG", "").strip()
    if ffmpeg:
        derived["ffmpeg"] = ffmpeg
        provenance.ffmpeg = "env"

    wav_backup = os.environ.get("TRANSCRIPTX_WAV_BACKUP_DIR", "").strip()
    if wav_backup:
        derived["wav_backup"] = wav_backup
        provenance.wav_backup = "env"

    if os.environ.get("INBOX_WATCH_AUDIO", "").strip():
        derived["watch_audio"] = _parse_bool_env(
            os.environ.get("INBOX_WATCH_AUDIO"), default=True
        )
    if os.environ.get("INBOX_WATCH_TRANSCRIPTS", "").strip():
        derived["watch_transcripts"] = _parse_bool_env(
            os.environ.get("INBOX_WATCH_TRANSCRIPTS"), default=True
        )
    if os.environ.get("INBOX_WATCH_BACKUP_WAV", "").strip():
        derived["backup_wavs"] = _parse_bool_env(
            os.environ.get("INBOX_WATCH_BACKUP_WAV"), default=False
        )
    if os.environ.get("INBOX_WATCH_DELETE_ORIGINALS", "").strip():
        derived["delete_originals"] = _parse_bool_env(
            os.environ.get("INBOX_WATCH_DELETE_ORIGINALS"), default=False
        )
    return derived, provenance


def base_config_dict() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "watch_audio": True,
        "watch_transcripts": True,
        "recursive": False,
        "interval_seconds": 5.0,
        "backup_wavs": False,
        "delete_originals": False,
    }


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
        return repo_root / ".transcriptx" / "inbox-watch.json"
    return Path.cwd() / ".inbox-watch-no-config.json"


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"ERROR: invalid config file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: config file must be a JSON object: {path}")
    for key in data:
        if key not in KNOWN_CONFIG_KEYS:
            print(f"WARNING: ignoring unknown config key: {key}", file=sys.stderr)
    return data


def _apply_path_layer(
    merged: dict[str, Any],
    provenance: ConfigProvenance,
    layer: dict[str, Any],
    source: ConfigSource,
) -> None:
    for key in _PATH_KEYS:
        value = layer.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        merged[key] = str(value)
        setattr(provenance, key, source)


def _as_optional_path(value: Any) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return Path(text).expanduser()


def resolve_config(
    args: argparse.Namespace, *, config_path: Path | None = None
) -> EffectiveConfig:
    repo_root = find_repo_root()
    if repo_root is not None:
        bootstrap_repo_env(repo_root)

    active_config = config_path or resolve_config_path(args)
    file_cfg = load_config(active_config)

    portable_layer, provenance = portable_defaults(repo_root)
    env_layer, env_prov = env_derived_config()

    merged: dict[str, Any] = {**base_config_dict(), **portable_layer}
    _apply_path_layer(merged, provenance, env_layer, "env")
    for key in _PATH_KEYS:
        if getattr(env_prov, key) != "unset":
            setattr(provenance, key, getattr(env_prov, key))
    for key, value in env_layer.items():
        if key not in _PATH_KEYS:
            merged[key] = value

    json_path_layer = {
        k: file_cfg[k] for k in _PATH_KEYS if k in file_cfg and file_cfg[k] is not None
    }
    _apply_path_layer(merged, provenance, json_path_layer, "json")
    for key in set(file_cfg) - set(_PATH_KEYS):
        merged[key] = file_cfg[key]

    if args.inbox is not None:
        merged["inbox"] = str(args.inbox)
        provenance.inbox = "cli"
    if args.recordings is not None:
        merged["recordings"] = str(args.recordings)
        provenance.recordings = "cli"
    if args.transcripts is not None:
        merged["transcripts"] = str(args.transcripts)
        provenance.transcripts = "cli"
    if args.env_file is not None:
        merged["env_file"] = str(args.env_file)
        provenance.env_file = "cli"
    if args.whispermlx_missing is not None:
        merged["whispermlx_missing"] = str(args.whispermlx_missing)
        provenance.whispermlx_missing = "cli"
    if args.ffmpeg is not None:
        merged["ffmpeg"] = str(args.ffmpeg)
        provenance.ffmpeg = "cli"
    if args.move_processed is not None:
        merged["move_processed"] = str(args.move_processed)
        provenance.move_processed = "cli"
    if args.wav_backup is not None:
        merged["wav_backup"] = str(args.wav_backup)
        provenance.wav_backup = "cli"
    if args.watch_audio is not None:
        merged["watch_audio"] = args.watch_audio
    if args.watch_transcripts is not None:
        merged["watch_transcripts"] = args.watch_transcripts
    if args.backup_wavs is not None:
        merged["backup_wavs"] = args.backup_wavs
    if args.delete_originals is not None:
        merged["delete_originals"] = args.delete_originals
    if args.recursive is not None:
        merged["recursive"] = args.recursive
    if args.interval_seconds is not None:
        merged["interval_seconds"] = args.interval_seconds

    watch_audio = require_bool(merged.get("watch_audio", True), "watch_audio")
    watch_transcripts = require_bool(
        merged.get("watch_transcripts", True), "watch_transcripts"
    )
    recursive = require_bool(merged.get("recursive", False), "recursive")
    backup_wavs = require_bool(merged.get("backup_wavs", False), "backup_wavs")
    delete_originals = require_bool(
        merged.get("delete_originals", False), "delete_originals"
    )
    interval = merged.get("interval_seconds", 5.0)
    try:
        interval_seconds = float(interval)
    except (TypeError, ValueError) as exc:
        raise SystemExit(
            f"ERROR: config key 'interval_seconds' must be a number, got {interval!r}"
        ) from exc

    return EffectiveConfig(
        inbox=_as_optional_path(merged.get("inbox")),
        recordings=_as_optional_path(merged.get("recordings")),
        transcripts=_as_optional_path(merged.get("transcripts")),
        env_file=_as_optional_path(merged.get("env_file")),
        whispermlx_missing=_as_optional_path(merged.get("whispermlx_missing")),
        ffmpeg=_as_optional_path(merged.get("ffmpeg")),
        watch_audio=watch_audio,
        watch_transcripts=watch_transcripts,
        recursive=recursive,
        interval_seconds=interval_seconds,
        move_processed=_as_optional_path(merged.get("move_processed")),
        wav_backup=_as_optional_path(merged.get("wav_backup")),
        backup_wavs=backup_wavs,
        delete_originals=delete_originals,
        provenance=provenance,
    )


def config_to_dict(cfg: EffectiveConfig) -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "inbox": str(cfg.inbox) if cfg.inbox else None,
        "recordings": str(cfg.recordings) if cfg.recordings else None,
        "transcripts": str(cfg.transcripts) if cfg.transcripts else None,
        "env_file": str(cfg.env_file) if cfg.env_file else None,
        "whispermlx_missing": (
            str(cfg.whispermlx_missing) if cfg.whispermlx_missing else None
        ),
        "ffmpeg": str(cfg.ffmpeg) if cfg.ffmpeg else None,
        "watch_audio": cfg.watch_audio,
        "watch_transcripts": cfg.watch_transcripts,
        "recursive": cfg.recursive,
        "interval_seconds": cfg.interval_seconds,
        "move_processed": str(cfg.move_processed) if cfg.move_processed else None,
        "wav_backup": str(cfg.wav_backup) if cfg.wav_backup else None,
        "backup_wavs": cfg.backup_wavs,
        "delete_originals": cfg.delete_originals,
    }


def save_config(cfg: EffectiveConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config_to_dict(cfg), indent=2) + "\n", encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def classify_path(path: Path | str) -> Kind:
    ext = Path(path).suffix.lower()
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in TRANSCRIPT_EXTENSIONS:
        return "transcript"
    return "ignore"


def is_same_or_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def find_stem_match(
    directory: Path, stem: str, extensions: frozenset[str]
) -> Path | None:
    if not directory.is_dir():
        return None
    stem_l = stem.lower()
    for candidate in directory.iterdir():
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in extensions:
            continue
        if candidate.stem.lower() == stem_l:
            return candidate
    return None


def wait_until_stable(
    path: Path,
    *,
    checks: int = 3,
    interval_ms: int = 500,
    timeout_ms: int = 30_000,
) -> bool:
    """Return True once size/mtime are unchanged for ``checks`` samples."""
    interval_s = max(interval_ms, 1) / 1000.0
    deadline = time.monotonic() + max(timeout_ms, interval_ms) / 1000.0
    previous: tuple[int, int] | None = None
    stable_count = 0
    while time.monotonic() < deadline:
        try:
            st = path.stat()
        except OSError:
            return False
        current = (int(st.st_size), int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))))
        if previous is not None and current == previous:
            stable_count += 1
            if stable_count >= max(checks, 1):
                return True
        else:
            stable_count = 1
            previous = current
            if max(checks, 1) == 1:
                return True
        time.sleep(interval_s)
    return previous is not None and stable_count >= max(checks, 1)


def discover_inbox_files(
    inbox: Path,
    *,
    recursive: bool,
    skip_under: Sequence[Path] | None = None,
) -> list[Path]:
    if not inbox.is_dir():
        return []
    if recursive:
        candidates = [p for p in inbox.rglob("*") if p.is_file()]
    else:
        candidates = [p for p in inbox.iterdir() if p.is_file()]
    skips = [p for p in (skip_under or []) if p is not None]
    out: list[Path] = []
    for path in candidates:
        if path.name.startswith("."):
            continue
        if any(is_same_or_under(path.parent, root) for root in skips):
            continue
        out.append(path)
    return sorted(out, key=lambda p: str(p).lower())


def build_ffmpeg_cmd(ffmpeg: str | Path, src: Path, dest: Path) -> list[str]:
    # Always pass -f mp3: dest may be a .mp3.partial temp path, and ffmpeg 8+
    # will not guess the muxer from a non-standard extension.
    return [
        str(ffmpeg),
        "-nostdin",
        "-y",
        "-i",
        str(src),
        "-ac",
        FFMPEG_CHANNELS,
        "-ar",
        FFMPEG_SAMPLE_RATE,
        "-c:a",
        FFMPEG_CODEC,
        "-b:a",
        FFMPEG_BITRATE,
        "-f",
        "mp3",
        str(dest),
    ]


def find_ffmpeg(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    found = shutil.which("ffmpeg")
    return Path(found) if found else None


def find_whispermlx_missing(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    found = shutil.which("whispermlx-missing")
    if found:
        return Path(found)
    repo_root = find_repo_root()
    if repo_root is not None:
        sibling = repo_root / "scripts" / "whispermlx-missing.py"
        if sibling.is_file():
            return sibling
    return None


def build_missing_cmd(
    missing: Path,
    *,
    recordings: Path,
    transcripts: Path,
    env_file: Path | None,
) -> list[str]:
    cmd: list[str]
    if missing.suffix.lower() == ".py":
        cmd = [sys.executable, str(missing)]
    else:
        cmd = [str(missing)]
    cmd.extend(["--source", str(recordings), "--transcripts", str(transcripts)])
    if env_file is not None:
        cmd.extend(["--env-file", str(env_file)])
    return cmd


def _human_bytes(n: int) -> str:
    if n >= 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024 * 1024):.1f} GiB"
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MiB"
    if n >= 1024:
        return f"{n / 1024:.1f} KiB"
    return f"{n} B"


def run_ffmpeg(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
    # Inherit stderr so ffmpeg's time=/speed= stats are visible on long encodes.
    return subprocess.run(cmd, check=False)


def run_whispermlx_missing(cmd: Sequence[str]) -> int:
    result = subprocess.run(cmd, check=False)
    return int(result.returncode)


def _move_processed(src: Path, dest_dir: Path) -> bool:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        print(
            f"WARNING: not moving {src.name}; {dest} already exists",
            file=sys.stderr,
        )
        return False
    shutil.move(str(src), str(dest))
    return True


def unique_backup_path(directory: Path, src: Path) -> Path:
    suffix = src.suffix.lower() or src.suffix
    dest = directory / f"{src.stem}{suffix}"
    counter = 1
    while dest.exists():
        dest = directory / f"{src.stem}_{counter}{suffix}"
        counter += 1
        if counter > 1000:
            raise OSError(f"too many name conflicts in {directory} for {src.stem}")
    return dest


def backup_original_to_wav(src: Path, wav_backup: Path) -> Path | None:
    wav_backup.mkdir(parents=True, exist_ok=True)
    dest = unique_backup_path(wav_backup, src)
    shutil.copy2(src, dest)
    print(f"Backed up: {src.name} -> {dest}")
    return dest


def finalize_inbox_source(
    src: Path,
    cfg: EffectiveConfig,
    *,
    kind: Kind,
    dry_run: bool,
    stats: CycleStats,
) -> None:
    """Backup / move / delete an inbox source after a successful convert or copy."""
    if kind == "audio" and cfg.backup_wavs:
        if cfg.wav_backup is None:
            print("ERROR: backup_wavs is on but wav_backup is unset", file=sys.stderr)
            return
        if dry_run:
            dest = unique_backup_path(cfg.wav_backup, src)
            print(f"Would backup: {src} -> {dest}")
            stats.would_backup += 1
        else:
            try:
                backup_original_to_wav(src, cfg.wav_backup)
                stats.originals_backed_up += 1
            except OSError as exc:
                print(f"ERROR: wav backup failed for {src.name}: {exc}", file=sys.stderr)
                if cfg.delete_originals:
                    print(
                        f"WARNING: not deleting {src.name} because backup failed",
                        file=sys.stderr,
                    )
                return

    if cfg.move_processed is not None:
        if dry_run:
            print(f"Would move: {src} -> {cfg.move_processed / src.name}")
            return
        if _move_processed(src, cfg.move_processed):
            print(f"Moved: {src.name} -> {cfg.move_processed / src.name}")
        return

    if cfg.delete_originals:
        if dry_run:
            print(f"Would delete original: {src}")
            stats.would_delete += 1
            return
        try:
            src.unlink()
        except OSError as exc:
            print(f"ERROR: could not delete {src.name}: {exc}", file=sys.stderr)
            return
        print(f"Deleted original: {src.name}")
        stats.originals_deleted += 1


def looks_like_managed_library_root(path: Path) -> bool:
    """True when *path* is the managed transcripts library root (not originals/).

    Host helpers must write raw engine JSON under ``…/transcripts/originals``,
    never into the library root beside ``metadata/`` / ``imports/``.
    """
    resolved = path.expanduser()
    if resolved.name == "originals":
        return False
    markers = ("metadata", "originals", "imports")
    try:
        return any((resolved / name).is_dir() for name in markers)
    except OSError:
        return False


def validate_layout(cfg: EffectiveConfig) -> str | None:
    if not cfg.watch_audio and not cfg.watch_transcripts:
        return "Enable at least one of watch_audio / watch_transcripts."
    if cfg.inbox is None:
        return "inbox is required."
    inbox = cfg.inbox
    if cfg.watch_audio:
        if cfg.recordings is None:
            return "recordings is required when watch_audio is on."
        if cfg.transcripts is None:
            return "transcripts is required when watch_audio is on (whispermlx-missing output)."
    if cfg.watch_transcripts and cfg.transcripts is None:
        return "transcripts is required when watch_transcripts is on."

    if cfg.transcripts is not None and looks_like_managed_library_root(cfg.transcripts):
        return (
            "transcripts must be the originals/ folder (e.g. …/transcripts/originals), "
            "not the managed library root that contains metadata/ or imports/. "
            "Raw engine JSON in the library root is not admitted until Import Transcript "
            "or Settings → Watcher runs."
        )

    dests: list[tuple[str, Path]] = []
    if cfg.recordings is not None:
        dests.append(("recordings", cfg.recordings))
    if cfg.transcripts is not None:
        dests.append(("transcripts", cfg.transcripts))
    for label, dest in dests:
        if inbox.resolve() == dest.resolve() or is_same_or_under(inbox, dest):
            return f"inbox must not be {label} or a path under {label}."
        if is_same_or_under(dest, inbox):
            return f"{label} must not be under inbox."
    if cfg.move_processed is not None:
        processed = cfg.move_processed
        if processed.resolve() == inbox.resolve():
            return "move_processed must not be the inbox."
        if cfg.delete_originals:
            return "Use either delete_originals or move_processed, not both."
    if cfg.backup_wavs:
        if cfg.wav_backup is None:
            return "wav_backup is required when backup_wavs is on."
        wav_backup = cfg.wav_backup
        if inbox.resolve() == wav_backup.resolve() or is_same_or_under(inbox, wav_backup):
            return "inbox must not be wav_backup or a path under wav_backup."
        if is_same_or_under(wav_backup, inbox):
            return "wav_backup must not be under inbox."
    return None


def _has_meaningful_paths(cfg: EffectiveConfig) -> bool:
    if cfg.provenance.inbox not in _MEANINGFUL_PATH_SOURCES:
        return False
    if cfg.watch_audio:
        if cfg.provenance.recordings not in _MEANINGFUL_PATH_SOURCES:
            return False
        if cfg.provenance.transcripts not in _MEANINGFUL_PATH_SOURCES:
            return False
    if cfg.watch_transcripts:
        if cfg.provenance.transcripts not in _MEANINGFUL_PATH_SOURCES:
            return False
    return True


def convert_audio(
    src: Path,
    recordings: Path,
    *,
    ffmpeg: Path,
    force: bool,
    dry_run: bool,
    cfg: EffectiveConfig,
    stats: CycleStats,
) -> str:
    """Return converted / skipped / failed / dry_run."""
    existing = find_stem_match(recordings, src.stem, AUDIO_EXTENSIONS)
    dest = recordings / f"{src.stem}.mp3"
    if existing is not None and not force:
        _log(f"  Skipping (stem exists): {src.name} -> {existing.name}")
        return "skipped"
    if dry_run:
        cmd = build_ffmpeg_cmd(ffmpeg, src, dest)
        _log(f"  Would convert: {' '.join(cmd)}")
        finalize_inbox_source(src, cfg, kind="audio", dry_run=True, stats=stats)
        return "dry_run"

    recordings.mkdir(parents=True, exist_ok=True)
    partial = recordings / f".inbox-watch.{src.stem}.mp3.partial"
    try:
        size = f" ({_human_bytes(src.stat().st_size)})"
    except OSError:
        size = ""
    _log(f"  Converting: {src.name} -> {dest.name}{size}")
    _log("  ffmpeg progress on stderr (time=/speed=)…")
    started = time.perf_counter()
    cmd = build_ffmpeg_cmd(ffmpeg, src, partial)
    result = run_ffmpeg(cmd)
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        if partial.exists():
            partial.unlink(missing_ok=True)
        extra = ""
        if result.stderr:
            tail = "\n".join(result.stderr.splitlines()[-20:])
            extra = f": {tail}"
        _log(
            f"ERROR: ffmpeg failed for {src.name} "
            f"(exit {result.returncode}, {elapsed:.1f}s){extra}",
            err=True,
        )
        return "failed"
    os.replace(partial, dest)
    try:
        out_size = f" ({_human_bytes(dest.stat().st_size)})"
    except OSError:
        out_size = ""
    _log(f"  Converted: {src.name} -> {dest.name}{out_size} in {elapsed:.1f}s")
    finalize_inbox_source(src, cfg, kind="audio", dry_run=False, stats=stats)
    return "converted"


def copy_transcript(
    src: Path,
    transcripts: Path,
    *,
    force: bool,
    dry_run: bool,
    cfg: EffectiveConfig,
    stats: CycleStats,
) -> str:
    existing = find_stem_match(transcripts, src.stem, TRANSCRIPT_EXTENSIONS)
    dest = transcripts / src.name
    if existing is not None and not force:
        _log(f"  Skipping (stem exists): {src.name} -> {existing.name}")
        return "skipped"
    if dry_run:
        _log(f"  Would copy: {src} -> {dest}")
        finalize_inbox_source(src, cfg, kind="transcript", dry_run=True, stats=stats)
        return "dry_run"

    transcripts.mkdir(parents=True, exist_ok=True)
    _log(f"  Copying: {src.name} -> {dest.name}")
    try:
        shutil.copy2(src, dest)
    except OSError as exc:
        _log(f"ERROR: copy failed for {src.name}: {exc}", err=True)
        return "failed"
    _log(f"  Copied: {src.name} -> {dest.name}")
    finalize_inbox_source(src, cfg, kind="transcript", dry_run=False, stats=stats)
    return "copied"


def print_review_before_cycle(
    cfg: EffectiveConfig,
    work: Sequence[tuple[Path, Kind]],
    *,
    dry_run: bool,
) -> None:
    audio_n = sum(1 for _, kind in work if kind == "audio")
    tx_n = sum(1 for _, kind in work if kind == "transcript")
    _print_section("Review before cycle")
    _log(f"  Mode:        {'dry-run' if dry_run else 'once'}")
    _log(f"  Inbox:       {cfg.inbox}")
    if cfg.watch_audio:
        _log(f"  Recordings:  {cfg.recordings}")
    if cfg.watch_transcripts or cfg.watch_audio:
        _log(f"  Transcripts: {cfg.transcripts}")
    modes: list[str] = []
    if cfg.watch_audio:
        modes.append("audio→mp3 + whispermlx-missing")
    if cfg.watch_transcripts:
        modes.append("transcript copy")
    _log(f"  Watching:    {', '.join(modes) if modes else '(none)'}")
    _log(f"  Candidates:  {len(work)} ({audio_n} audio, {tx_n} transcript)")
    if work:
        preview = [f"{kind}: {src.name}" for src, kind in work]
        _print_limited_items("Will consider", preview, limit=12)
    else:
        _log("  Will consider: (none)")
    _log("---")


def maybe_run_missing(
    cfg: EffectiveConfig,
    stats: CycleStats,
    *,
    missing: Path,
    dry_run: bool,
) -> None:
    assert cfg.recordings is not None
    assert cfg.transcripts is not None
    cmd = build_missing_cmd(
        missing,
        recordings=cfg.recordings,
        transcripts=cfg.transcripts,
        env_file=cfg.env_file,
    )
    _print_section("Transcription (whispermlx-missing)")
    if dry_run:
        _log(f"  Would run: {' '.join(cmd)}")
        stats.would_invoke_missing += 1
        _log("---")
        return
    _log(f"  Running: {' '.join(cmd)}")
    _log("  (child process output follows)")
    started = time.perf_counter()
    rc = run_whispermlx_missing(cmd)
    elapsed = time.perf_counter() - started
    stats.missing_invoked += 1
    if rc != 0:
        _log(
            f"WARNING: whispermlx-missing exited {rc} after {elapsed:.1f}s",
            err=True,
        )
        stats.failed_names.append("whispermlx-missing")
        stats.audio_failed += 1
    else:
        _log(f"  Finished whispermlx-missing in {elapsed:.1f}s")
    _log("---")


def process_cycle(
    cfg: EffectiveConfig,
    *,
    dry_run: bool,
    force: bool,
    ffmpeg: Path | None,
    stability_checks: int,
    stability_interval_ms: int,
    stability_timeout_ms: int,
) -> CycleStats:
    assert cfg.inbox is not None
    stats = CycleStats()
    files = discover_inbox_files(
        cfg.inbox,
        recursive=cfg.recursive,
        skip_under=[p for p in (cfg.move_processed, cfg.wav_backup) if p is not None],
    )
    work: list[tuple[Path, Kind]] = []
    for src in files:
        kind = classify_path(src)
        if kind == "audio" and not cfg.watch_audio:
            continue
        if kind == "transcript" and not cfg.watch_transcripts:
            continue
        if kind == "ignore":
            continue
        work.append((src, kind))

    print_review_before_cycle(cfg, work, dry_run=dry_run)
    total = len(work)
    if total == 0:
        _log("No inbox candidates this cycle.")
        return stats

    _print_section("Processing")
    for index, (src, kind) in enumerate(work, start=1):
        _log(f"[{index}/{total}] {kind}: {src.name}")
        if not wait_until_stable(
            src,
            checks=stability_checks,
            interval_ms=stability_interval_ms,
            timeout_ms=stability_timeout_ms,
        ):
            _log(f"  Unstable (skipped this cycle): {src.name}", err=True)
            stats.unstable += 1
            stats.unstable_names.append(src.name)
            continue
        if kind == "audio":
            assert cfg.recordings is not None
            assert ffmpeg is not None
            outcome = convert_audio(
                src,
                cfg.recordings,
                ffmpeg=ffmpeg,
                force=force,
                dry_run=dry_run,
                cfg=cfg,
                stats=stats,
            )
            if outcome == "converted":
                stats.audio_converted += 1
                stats.converted_names.append(src.name)
            elif outcome == "dry_run":
                stats.would_convert += 1
                stats.converted_names.append(src.name)
            elif outcome == "skipped":
                stats.audio_skipped += 1
                stats.skipped_names.append((src.name, "stem exists in recordings"))
            else:
                stats.audio_failed += 1
                stats.failed_names.append(src.name)
        elif kind == "transcript":
            assert cfg.transcripts is not None
            outcome = copy_transcript(
                src,
                cfg.transcripts,
                force=force,
                dry_run=dry_run,
                cfg=cfg,
                stats=stats,
            )
            if outcome == "copied":
                stats.transcripts_copied += 1
                stats.copied_names.append(src.name)
            elif outcome == "dry_run":
                stats.would_copy += 1
                stats.copied_names.append(src.name)
            elif outcome == "skipped":
                stats.transcripts_skipped += 1
                stats.skipped_names.append((src.name, "stem exists in transcripts"))
            else:
                stats.transcripts_failed += 1
                stats.failed_names.append(src.name)

    _log("---")
    return stats


def print_summary(
    stats: CycleStats,
    cfg: EffectiveConfig,
    *,
    dry_run: bool,
) -> None:
    status = _cycle_status(stats, dry_run=dry_run)
    _print_section("Run summary")
    _log(f"  Status:   {status}")
    if cfg.inbox is not None:
        _log(f"  Inbox:    {cfg.inbox}")
    if cfg.watch_audio and cfg.recordings is not None:
        _log(f"  Outputs:  {cfg.recordings}")
    if (cfg.watch_transcripts or cfg.watch_audio) and cfg.transcripts is not None:
        _log(f"  Transcripts: {cfg.transcripts}")

    if dry_run:
        _log(f"  Would convert: {stats.would_convert}")
        _log(f"  Would copy:    {stats.would_copy}")
        _log(f"  Would invoke missing: {stats.would_invoke_missing}")
        _log(f"  Would backup:  {stats.would_backup}")
        _log(f"  Would delete:  {stats.would_delete}")
        _print_limited_items("Would convert", stats.converted_names)
        _print_limited_items("Would copy", stats.copied_names)
    else:
        _log(f"  Converted: {stats.audio_converted}")
        _log(f"  Copied:    {stats.transcripts_copied}")
        _log(f"  Backed up: {stats.originals_backed_up}")
        _log(f"  Deleted:   {stats.originals_deleted}")
        _log(f"  Missing runs: {stats.missing_invoked}")
        _print_limited_items("Converted", stats.converted_names)
        _print_limited_items("Copied", stats.copied_names)

    if stats.skipped_names:
        _log("  Skipped:")
        for name, reason in stats.skipped_names[:12]:
            _log(f"    • {name} ({reason})")
        if len(stats.skipped_names) > 12:
            _log(f"    • ... and {len(stats.skipped_names) - 12} more")
    else:
        skipped_n = stats.audio_skipped + stats.transcripts_skipped
        _log(f"  Skipped:  {skipped_n}")

    if stats.unstable_names:
        _print_limited_items("Unstable", stats.unstable_names)
    elif stats.unstable:
        _log(f"  Unstable: {stats.unstable}")

    if stats.failed_names:
        _print_limited_items("Failed", stats.failed_names)
    else:
        _log(f"  Failed:   {stats.failed}")

    if not dry_run and (stats.audio_converted or stats.transcripts_copied):
        _log("  Next: import transcripts in the web UI if they are not managed yet")
    _log("---")
    _log()


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(line_buffering=True)
            except (OSError, ValueError):
                pass
    args = parse_args(argv)
    config_path = resolve_config_path(args)
    cfg = resolve_config(args, config_path=config_path)

    if args.show_config:
        print(json.dumps(config_to_dict(cfg), indent=2))
        return 0

    if args.save_config:
        save_config(cfg, config_path)
        print(f"Saved config: {config_path}")

    if not _has_meaningful_paths(cfg):
        print(
            "Nothing to do. Set inbox (and recordings/transcripts as required) via CLI, "
            ".transcriptx/inbox-watch.json, or INBOX_WATCH_* / TRANSCRIPTX_* env; "
            "or use --show-config / --save-config.",
            file=sys.stderr,
        )
        return 2

    layout_error = validate_layout(cfg)
    if layout_error:
        print(f"ERROR: {layout_error}", file=sys.stderr)
        return 2
    if cfg.delete_originals and not cfg.backup_wavs and cfg.move_processed is None:
        print(
            "WARNING: originals will be deleted with no WAV backup. "
            "Pass --backup-wav unless you are sure you do not need the inbox files.",
            file=sys.stderr,
        )

    assert cfg.inbox is not None
    if not args.dry_run and not cfg.inbox.is_dir():
        print(f"ERROR: inbox is not a directory: {cfg.inbox}", file=sys.stderr)
        return 2

    ffmpeg: Path | None = None
    missing: Path | None = None
    if cfg.watch_audio:
        ffmpeg = find_ffmpeg(cfg.ffmpeg)
        if ffmpeg is None and not args.dry_run:
            print("ERROR: ffmpeg not found (set --ffmpeg or PATH).", file=sys.stderr)
            return 2
        if ffmpeg is None:
            ffmpeg = Path("ffmpeg")
        missing = find_whispermlx_missing(cfg.whispermlx_missing)
        if missing is None and not args.dry_run:
            print(
                "ERROR: whispermlx-missing not found "
                "(set --whispermlx-missing or install the sibling script).",
                file=sys.stderr,
            )
            return 2
        if missing is None:
            missing = Path("whispermlx-missing")

    watch_loop = bool(args.watch_loop)
    first = True
    total_failed = 0
    try:
        while True:
            stats = process_cycle(
                cfg,
                dry_run=args.dry_run,
                force=args.force,
                ffmpeg=ffmpeg,
                stability_checks=args.stability_checks,
                stability_interval_ms=args.stability_interval_ms,
                stability_timeout_ms=args.stability_timeout_ms,
            )
            wrote_audio = stats.audio_converted > 0 or stats.would_convert > 0
            if cfg.watch_audio and missing is not None:
                if (not watch_loop) or first or wrote_audio:
                    maybe_run_missing(
                        cfg, stats, missing=missing, dry_run=args.dry_run
                    )
            print_summary(stats, cfg, dry_run=args.dry_run)
            total_failed += stats.failed
            if not watch_loop:
                break
            first = False
            time.sleep(max(cfg.interval_seconds, 0.1))
    except KeyboardInterrupt:
        _log()
        _log("Stopped.")
        return 0 if total_failed == 0 else 1

    return 1 if total_failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
