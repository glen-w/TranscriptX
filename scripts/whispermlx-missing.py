#!/usr/bin/env python3
"""
Batch transcription orchestrator for whispermlx — process MP3s missing JSON transcripts.

Install:
    install -m 755 scripts/whispermlx-missing.py ~/.local/bin/whispermlx-missing
    (ensure ~/.local/bin is on PATH)

First run (save paths, then process when folders exist):
    whispermlx-missing \\
        --source /audio \\
        --transcripts /transcripts \\
        --save-config

Save config only (no source/transcripts on CLI or in saved config):
    whispermlx-missing --env-file /path/to/whisperx.env --save-config

Extra whispermlx flags (use equals form, or --whisper-args at end of command):
    --whisper-arg=--batch_size --whisper-arg 16
    --whisper-args --batch_size 16 --temperature 0

Normal run (uses config file; see --config):
    whispermlx-missing

Config file (default .transcriptx/whispermlx-missing.json when run from repo):
    --config /path/to/config.json
    or env WHISPERMLX_MISSING_CONFIG=/path/to/config.json

Config sources (merge order: portable defaults <- env <- local JSON <- CLI):
    Paths from portable defaults alone do not trigger processing on a fresh clone.
    Set paths via CLI, .transcriptx/whispermlx-missing.json, or TRANSCRIPTX_* env.
    TRANSCRIPTX_TRANSCRIPTS_DIR is the transcripts base; the script appends /originals.
    JSON/CLI --transcripts is the exact output directory (no /originals append).
    whisperx.env is used only for the whispermlx subprocess environment (HF_TOKEN).

Dry run:
    whispermlx-missing --dry-run

Dry-run uses lightweight validation (source/transcripts paths and source folder only).
It does not require env file, HF_TOKEN, or a working whispermlx binary.

Already-processed detection (flat folders, JSON only):
    For MP3 stem ``foo``, skip if any of these exist in --transcripts:
    foo.json, foo.diarized.json, foo_diarized.json, foo.diarised.json, foo_diarised.json
    Also skip foo (N).json (import-archive disambiguation).
    When --transcripts is ``…/originals``, also search the parent library root so
    already-imported canonical JSON counts as done. Sidecar JSON next to the MP3
    in --source is also treated as done.
    With --fuzzy-json-match, also match foo-<rest>.json, foo_<rest>.json, foo.<rest>.json
    (never matches foo2.json for stem foo).

Skip likely serial parts (--skip-serial, off by default):
    Do not transcribe MP3s that Auto-merge would group as split parts / voice-note
    runs (meeting_part2, timestamp_1/_2, WhatsApp bursts, …). Merge those files in
    Tools → Auto-merge and transcribe the ``*_merged.mp3`` instead. Groups marked
    **Don't suggest again** on Auto-merge are not skipped (they are treated as
    separate recordings). ``--force`` still skips serial members; use
    ``--no-skip-serial`` to transcribe parts anyway. JSON ``skip_serial`` / env
    WHISPERMLX_SKIP_SERIAL also enable it. Uses the Auto-merge detector when
    TranscriptX is importable; otherwise filename + common voice-note rules.

Failure handling:
    Failed items leave temp dirs under transcripts/.whispermlx-missing/tmp/ for inspection.
    No partial JSON is written to the transcripts root. Use --clean-failed to remove failed temps.
    Exit 0 = all ok; 1 = one or more item failures; 2 = CLI/config/validation error.

HF_TOKEN:
    Passed via subprocess environment by default (not argv). Use --pass-hf-token-arg only if
    env propagation fails (less secure — token may appear in process listings or live output).

Live output:
    Real processing streams whispermlx stdout/stderr to your terminal by default.
    Use --quiet for captured output and stderr tails on failure (unattended batch mode).

Output format:
    Verify locally: whispermlx --help | grep output_format
    Default uses -f json when supported; --no-output-format-flag disables it.
    Post-run JSON discovery and non-JSON cleanup are the real safety net.

--save-config alone (no processing paths): saves and exits with warnings.
--save-config with --source/--transcripts (CLI or saved config), or with --dry-run:
    saves first, then validates and processes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

CONFIG_VERSION = 1
CONFIG_PATH: Path | None = None  # tests may monkeypatch; else repo .transcriptx default
CONFIG_ENV_VAR = "WHISPERMLX_MISSING_CONFIG"

ConfigSource = Literal["cli", "json", "env", "portable", "unset"]
_MEANINGFUL_PATH_SOURCES = frozenset({"cli", "json", "env"})

KNOWN_CONFIG_KEYS = frozenset(
    {
        "version",
        "source",
        "transcripts",
        "env_file",
        "whispermlx",
        "model",
        "language",
        "diarize",
        "output_format",
        "use_output_format_flag",
        "clean_non_json",
        "extra_whisper_args",
        "pass_hf_token_arg",
        "fuzzy_json_match",
        "skip_serial",
        "follow_output",
    }
)

_EXACT_SUFFIXES = (
    ".json",
    ".diarized.json",
    "_diarized.json",
    ".diarised.json",
    "_diarised.json",
)

_ENV_LINE_RE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

DRY_RUN_LIST_LIMIT = 10


@dataclass
class FailedItem:
    mp3_name: str
    reason: str
    exit_code: int | None = None
    temp_dir: Path | None = None


@dataclass
class RunStats:
    processed: int = 0
    would_process: int = 0
    skipped: int = 0
    skipped_serial: int = 0
    failed: int = 0
    would_process_names: list[str] = field(default_factory=list)
    skipped_serial_names: list[str] = field(default_factory=list)
    failed_items: list[FailedItem] = field(default_factory=list)


@dataclass
class ConfigProvenance:
    source: ConfigSource = "unset"
    transcripts: ConfigSource = "unset"
    env_file: ConfigSource = "unset"
    whispermlx: ConfigSource = "unset"


@dataclass
class EffectiveConfig:
    source: Path | None
    transcripts: Path | None
    env_file: Path
    whispermlx: Path
    model: str
    language: str
    diarize: bool
    output_format: str
    use_output_format_flag: bool
    clean_non_json: bool
    extra_whisper_args: list[str]
    pass_hf_token_arg: bool
    fuzzy_json_match: bool
    skip_serial: bool = False
    follow_output: bool = True
    provenance: ConfigProvenance = field(default_factory=ConfigProvenance)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe MP3s that are missing JSON transcripts (whispermlx batch).",
    )
    parser.add_argument(
        "--config",
        "--config-file",
        dest="config",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Config JSON path (default: .transcriptx/whispermlx-missing.json in repo). "
            f"Override with {CONFIG_ENV_VAR} env var."
        ),
    )
    parser.add_argument("--source", "--folder1", dest="source", type=Path, default=None)
    parser.add_argument(
        "--transcripts", "--folder2", dest="transcripts", type=Path, default=None
    )
    parser.add_argument("--env-file", dest="env_file", type=Path, default=None)
    parser.add_argument("--whispermlx", dest="whispermlx", type=Path, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--language", default=None)
    parser.add_argument(
        "--no-diarize",
        action="store_true",
        help="Disable diarization (default: diarize on).",
    )
    parser.add_argument("--output-format", dest="output_format", default=None)
    parser.add_argument(
        "--no-output-format-flag",
        action="store_true",
        help="Do not pass -f/--output_format to whispermlx.",
    )
    parser.add_argument(
        "--whisper-arg",
        dest="whisper_args",
        action="append",
        default=None,
        metavar="ARG",
        help=(
            "Extra whispermlx argument (repeatable). For flags, use equals form: "
            "--whisper-arg=--batch_size --whisper-arg 16"
        ),
    )
    parser.add_argument(
        "--whisper-args",
        dest="whisper_args_tail",
        nargs=argparse.REMAINDER,
        default=None,
        help=(
            "Remaining whispermlx args as one tail (must be last on the command line). "
            "Example: --whisper-args --batch_size 16 --temperature 0"
        ),
    )
    parser.add_argument(
        "--save-config",
        action="store_true",
        help="Save resolved settings to the config file (see --config).",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Print effective config and exit (no path validation).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would run without executing whispermlx.",
    )
    parser.add_argument(
        "--force",
        "--rerun",
        dest="force",
        action="store_true",
        help="Process even when matching JSON exists; replace after valid new JSON.",
    )
    parser.add_argument(
        "--fuzzy-json-match",
        action="store_true",
        help="Also skip when foo-<rest>.json, foo_<rest>.json, or foo.<rest>.json exists.",
    )
    serial_group = parser.add_mutually_exclusive_group()
    serial_group.add_argument(
        "--skip-serial",
        dest="skip_serial",
        action="store_true",
        default=None,
        help=(
            "Do not transcribe MP3s that look like Auto-merge serial groups "
            "(split parts / voice-note runs). Merge first, then transcribe "
            "the merged file."
        ),
    )
    serial_group.add_argument(
        "--no-skip-serial",
        dest="skip_serial",
        action="store_false",
        help="Transcribe serial parts (default unless config/env enables skip).",
    )
    parser.add_argument(
        "--pass-hf-token-arg",
        action="store_true",
        help="Pass HF_TOKEN via --hf_token (less secure; use only if env fails).",
    )
    parser.add_argument(
        "--clean-failed",
        action="store_true",
        help="Remove failed per-file temp dirs after the run.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep successful per-file temp dirs for debugging.",
    )
    parser.add_argument(
        "--no-clean-non-json",
        action="store_true",
        help="Keep non-JSON sidecar files in temp dirs (debug whispermlx output).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Capture whispermlx output (no live stream); show stderr tail on failure.",
    )
    parser.set_defaults(skip_serial=None)
    return parser.parse_args(argv)


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


def require_str(value: Any, key: str) -> str:
    if not isinstance(value, str):
        raise SystemExit(
            f"ERROR: config key {key!r} must be a string, got {type(value).__name__}"
        )
    return value


def require_list_of_str(value: Any, key: str) -> list[str]:
    if not isinstance(value, list):
        raise SystemExit(
            f"ERROR: config key {key!r} must be a list, got {type(value).__name__}"
        )
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise SystemExit(
                f"ERROR: config key {key!r}[{index}] must be a string, "
                f"got {type(item).__name__}"
            )
        result.append(item)
    return result


def find_repo_root() -> Path | None:
    """Return repo root when script lives at scripts/whispermlx-missing.py."""
    script_dir = Path(__file__).resolve().parent
    if script_dir.name != "scripts":
        return None
    return script_dir.parent


def bootstrap_repo_env(repo_root: Path) -> None:
    """Load repo .env into os.environ without overriding existing shell values."""
    dotenv_path = repo_root / ".env"
    for key, value in parse_env_file(dotenv_path).items():
        os.environ.setdefault(key, value)


def portable_defaults(
    repo_root: Path | None,
) -> tuple[dict[str, Any], ConfigProvenance]:
    """Repo-relative path suggestions when no higher layer provides a value."""
    provenance = ConfigProvenance()
    defaults: dict[str, Any] = {}
    if repo_root is None:
        return defaults, provenance

    defaults["source"] = str(repo_root / "data" / "recordings")
    provenance.source = "portable"
    defaults["transcripts"] = str(repo_root / "data" / "transcripts" / "originals")
    provenance.transcripts = "portable"
    defaults["env_file"] = str(repo_root / "whisperx.env")
    provenance.env_file = "portable"

    whispermlx_bin = shutil.which("whispermlx")
    if whispermlx_bin:
        defaults["whispermlx"] = whispermlx_bin
        provenance.whispermlx = "portable"
    else:
        defaults["whispermlx"] = ""
        provenance.whispermlx = "unset"

    return defaults, provenance


def _parse_bool_env(value: str | None, *, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in ("true", "1", "yes", "on"):
        return True
    if normalized in ("false", "0", "no", "off"):
        return False
    return default


def env_derived_config() -> tuple[dict[str, Any], ConfigProvenance]:
    """Build path config from os.environ (after optional repo .env bootstrap)."""
    provenance = ConfigProvenance()
    derived: dict[str, Any] = {}

    recordings = os.environ.get("TRANSCRIPTX_RECORDINGS_DIR", "").strip()
    if recordings:
        derived["source"] = recordings
        provenance.source = "env"

    transcripts_base = os.environ.get("TRANSCRIPTX_TRANSCRIPTS_DIR", "").strip()
    if transcripts_base:
        derived["transcripts"] = str(Path(transcripts_base).expanduser() / "originals")
        provenance.transcripts = "env"

    whispermlx_bin = os.environ.get("WHISPERMLX", "").strip()
    if whispermlx_bin:
        derived["whispermlx"] = whispermlx_bin
        provenance.whispermlx = "env"

    model = os.environ.get("WHISPERMLX_MODEL", "").strip()
    if model:
        derived["model"] = model
    language = os.environ.get("WHISPERMLX_LANGUAGE", "").strip()
    if language:
        derived["language"] = language
    if os.environ.get("WHISPERMLX_DIARIZE", "").strip():
        derived["diarize"] = _parse_bool_env(
            os.environ.get("WHISPERMLX_DIARIZE"), default=True
        )
    if os.environ.get("WHISPERMLX_SKIP_SERIAL", "").strip():
        derived["skip_serial"] = _parse_bool_env(
            os.environ.get("WHISPERMLX_SKIP_SERIAL"), default=False
        )

    return derived, provenance


def base_config_dict() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "model": "large-v3",
        "language": "en",
        "diarize": True,
        "output_format": "json",
        "use_output_format_flag": True,
        "clean_non_json": True,
        "extra_whisper_args": [],
        "pass_hf_token_arg": False,
        "fuzzy_json_match": False,
        "skip_serial": False,
        "follow_output": True,
    }


_PATH_KEYS = ("source", "transcripts", "env_file", "whispermlx")


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
            if key == "whispermlx":
                continue
            continue
        merged[key] = str(value)
        setattr(provenance, key, source)


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
        return repo_root / ".transcriptx" / "whispermlx-missing.json"
    return Path.cwd() / ".whispermlx-missing-no-config.json"


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


def config_to_dict(cfg: EffectiveConfig) -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "source": str(cfg.source) if cfg.source else None,
        "transcripts": str(cfg.transcripts) if cfg.transcripts else None,
        "env_file": str(cfg.env_file),
        "whispermlx": str(cfg.whispermlx),
        "model": cfg.model,
        "language": cfg.language,
        "diarize": cfg.diarize,
        "output_format": cfg.output_format,
        "use_output_format_flag": cfg.use_output_format_flag,
        "clean_non_json": cfg.clean_non_json,
        "extra_whisper_args": list(cfg.extra_whisper_args),
        "pass_hf_token_arg": cfg.pass_hf_token_arg,
        "fuzzy_json_match": cfg.fuzzy_json_match,
        "skip_serial": cfg.skip_serial,
        "follow_output": cfg.follow_output,
    }


def save_config(cfg: EffectiveConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(config_to_dict(cfg), indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


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
    if "skip_serial" in env_layer:
        merged["skip_serial"] = env_layer["skip_serial"]

    json_path_layer = {
        k: file_cfg[k] for k in _PATH_KEYS if k in file_cfg and file_cfg[k] is not None
    }
    _apply_path_layer(merged, provenance, json_path_layer, "json")

    for key in set(file_cfg) - set(_PATH_KEYS):
        merged[key] = file_cfg[key]

    if args.source is not None:
        merged["source"] = str(args.source)
        provenance.source = "cli"
    if args.transcripts is not None:
        merged["transcripts"] = str(args.transcripts)
        provenance.transcripts = "cli"
    if args.env_file is not None:
        merged["env_file"] = str(args.env_file)
        provenance.env_file = "cli"
    if args.whispermlx is not None:
        merged["whispermlx"] = str(args.whispermlx)
        provenance.whispermlx = "cli"
    if args.model is not None:
        merged["model"] = args.model
    if args.language is not None:
        merged["language"] = args.language
    if args.no_diarize:
        merged["diarize"] = False
    if args.output_format is not None:
        merged["output_format"] = args.output_format
    if args.no_output_format_flag:
        merged["use_output_format_flag"] = False
    if args.whisper_args is not None:
        merged["extra_whisper_args"] = list(args.whisper_args)
    if args.whisper_args_tail:
        base = list(merged.get("extra_whisper_args") or [])
        base.extend(args.whisper_args_tail)
        merged["extra_whisper_args"] = base
    if args.pass_hf_token_arg:
        merged["pass_hf_token_arg"] = True
    if args.fuzzy_json_match:
        merged["fuzzy_json_match"] = True
    if args.skip_serial is not None:
        merged["skip_serial"] = args.skip_serial
    if args.no_clean_non_json:
        merged["clean_non_json"] = False
    if args.quiet:
        merged["follow_output"] = False

    source = Path(merged["source"]).expanduser() if merged.get("source") else None
    transcripts = (
        Path(merged["transcripts"]).expanduser() if merged.get("transcripts") else None
    )

    whispermlx_raw = require_str(merged.get("whispermlx", ""), "whispermlx")
    whispermlx_path = Path(whispermlx_raw).expanduser() if whispermlx_raw else Path()

    extra = require_list_of_str(
        merged.get("extra_whisper_args") or [], "extra_whisper_args"
    )

    env_file_raw = require_str(merged.get("env_file", ""), "env_file")
    env_file_path = Path(env_file_raw).expanduser()
    if not env_file_path.is_absolute() and repo_root is not None:
        env_file_path = (repo_root / env_file_path).resolve()

    return EffectiveConfig(
        source=source,
        transcripts=transcripts,
        env_file=env_file_path,
        whispermlx=whispermlx_path,
        model=require_str(merged["model"], "model"),
        language=require_str(merged["language"], "language"),
        diarize=require_bool(merged["diarize"], "diarize"),
        output_format=require_str(merged["output_format"], "output_format"),
        use_output_format_flag=require_bool(
            merged["use_output_format_flag"], "use_output_format_flag"
        ),
        clean_non_json=require_bool(merged["clean_non_json"], "clean_non_json"),
        extra_whisper_args=extra,
        pass_hf_token_arg=require_bool(
            merged["pass_hf_token_arg"], "pass_hf_token_arg"
        ),
        fuzzy_json_match=require_bool(merged["fuzzy_json_match"], "fuzzy_json_match"),
        skip_serial=require_bool(merged.get("skip_serial", False), "skip_serial"),
        follow_output=require_bool(merged["follow_output"], "follow_output"),
        provenance=provenance,
    )


def print_effective_config(cfg: EffectiveConfig) -> None:
    print(json.dumps(config_to_dict(cfg), indent=2))
    print(
        "Note: output format flag probe not run for --show-config; "
        "see processing/dry-run output.",
        file=sys.stderr,
    )


def describe_output_format_note(
    cfg: EffectiveConfig, *, output_format_supported: bool | None = None
) -> str:
    if not cfg.use_output_format_flag:
        return "Note: output format flag disabled (--no-output-format-flag or config)."
    if output_format_supported is None:
        if cfg.whispermlx.is_file():
            output_format_supported = probe_output_format_support(cfg.whispermlx)
        else:
            return (
                f"Note: would request -f {cfg.output_format} when whispermlx is "
                "available (binary not found for --help probe)."
            )
    if output_format_supported:
        return f"Note: will pass -f {cfg.output_format} to whispermlx (verified via --help)."
    return (
        f"Note: config requests -f {cfg.output_format}, but whispermlx --help does "
        "not advertise output_format/-f; the flag will be omitted at run time."
    )


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE_RE.match(line)
        if not match:
            continue
        key, value = match.group(1), _strip_quotes(match.group(2))
        result[key] = value
    return result


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def discover_mp3s(source_dir: Path) -> list[Path]:
    if not source_dir.is_dir():
        return []
    mp3s = [
        p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() == ".mp3"
    ]
    return sorted(mp3s, key=lambda p: p.name.lower())


# --- serial skip (same groups Auto-merge would join) ---

_MERGED_OUTPUT_RE = re.compile(r"_merged\.mp3$", re.IGNORECASE)
_TIMESTAMP_SUFFIX_RE = re.compile(r"^(\d{8,})[_-](\d+)$")
_TIMESTAMP_BARE_RE = re.compile(r"^(\d{8,})$")
_PART_SUFFIX_RE = re.compile(
    r"^(.+?)(?:[\s_.-]+)?part(?:[\s_.-]+)?(\d+)$",
    re.IGNORECASE,
)
_NUMERIC_INDEX_RE = re.compile(r"^(.+?)[_-](\d{2,})$")
_DUPLICATE_INDEX_RE = re.compile(r" \(([1-9]\d{0,2})\)$")
_RE_WA_AT = re.compile(
    r"^(?P<family>WhatsApp(?:\s+(?:Audio|PTT|Voice\s+Notes?))?|"
    r"Voice\s+Notes?|Voice\s+Memos?|Voice\s+Messages?)"
    r"\s+(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})"
    r"\s+at\s+(?P<H>\d{1,2})[.:](?P<M>\d{2})[.:](?P<S>\d{2})$",
    re.IGNORECASE,
)
_RE_WA_ANDROID = re.compile(
    r"^(?P<kind>PTT|AUD)-(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})"
    r"-WA(?P<seq>\d{3,5})$",
    re.IGNORECASE,
)
_RE_TELEGRAM_AUDIO = re.compile(
    r"^audio_(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})"
    r"_(?P<H>\d{2})-(?P<M>\d{2})-(?P<S>\d{2})"
    r"(?:_[0-9a-fA-F]+)?$",
    re.IGNORECASE,
)
_RE_ZOOM_SEQ = re.compile(r"^ZOOM(?P<seq>\d{3,5})$", re.IGNORECASE)

_LITE_RULE_PRIORITY = (
    "timestamp_suffix",
    "part_suffix",
    "voice_note_run",
    "numeric_index",
    "duplicate_suffix",
)
_LITE_VOICE_GAP_SECONDS = 20 * 60
_LITE_MAX_INDEX_GAP = 3
_LITE_MIN_GROUP = 2


@dataclass(frozen=True)
class _LiteSerialGroup:
    base_key: str
    ordered_paths: tuple[Path, ...]
    matched_rule: str


def _strip_duplicate_stem(stem: str) -> str:
    return re.sub(r" \(([1-9]\d{0,2})\)$", "", stem or "")


def _lite_ymd_hms(
    y: int, mo: int, d: int, hour: int, minute: int, second: int
) -> datetime | None:
    try:
        return datetime(y, mo, d, hour, minute, second)
    except ValueError:
        return None


def _lite_normalize_paths(paths: Sequence[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        if _MERGED_OUTPUT_RE.search(resolved.name):
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def _lite_parse_timestamp(stem: str) -> tuple[str, int] | None:
    match = _TIMESTAMP_SUFFIX_RE.match(stem)
    if match:
        return match.group(1), int(match.group(2))
    match = _TIMESTAMP_BARE_RE.match(stem)
    if match:
        return match.group(1), 0
    return None


def _lite_parse_part(stem: str) -> tuple[str, int] | None:
    match = _PART_SUFFIX_RE.match(stem)
    if not match:
        return None
    base = match.group(1).rstrip("._- ")
    if not base:
        return None
    return base, int(match.group(2))


def _lite_parse_numeric(stem: str) -> tuple[str, int] | None:
    if _TIMESTAMP_SUFFIX_RE.match(stem):
        return None
    match = _NUMERIC_INDEX_RE.match(stem)
    if not match:
        return None
    base = match.group(1).rstrip("._- ")
    if not base or base.isdigit():
        return None
    return base, int(match.group(2))


def _lite_parse_duplicate(stem: str) -> tuple[str, int]:
    match = _DUPLICATE_INDEX_RE.search(stem)
    if match:
        return _strip_duplicate_stem(stem), int(match.group(1))
    return _strip_duplicate_stem(stem), 0


def _lite_parse_voice_note(
    stem: str,
) -> tuple[str, datetime | None, int | None] | None:
    s = _strip_duplicate_stem((stem or "").strip())
    if not s:
        return None
    match = _RE_WA_AT.match(s)
    if match:
        dt = _lite_ymd_hms(
            int(match["y"]),
            int(match["m"]),
            int(match["d"]),
            int(match["H"]),
            int(match["M"]),
            int(match["S"]),
        )
        if dt is None:
            return None
        return "WhatsApp Audio", dt, None
    match = _RE_TELEGRAM_AUDIO.match(s)
    if match:
        dt = _lite_ymd_hms(
            int(match["y"]),
            int(match["m"]),
            int(match["d"]),
            int(match["H"]),
            int(match["M"]),
            int(match["S"]),
        )
        if dt is None:
            return None
        return "Telegram Audio", dt, None
    match = _RE_WA_ANDROID.match(s)
    if match:
        try:
            dt = datetime(int(match["y"]), int(match["m"]), int(match["d"]))
        except ValueError:
            return None
        family = (
            "WhatsApp Voice Notes"
            if match["kind"].upper() == "PTT"
            else "WhatsApp Audio"
        )
        return family, dt, int(match["seq"])
    match = _RE_ZOOM_SEQ.match(s)
    if match:
        return "Zoom Recorder", None, int(match["seq"])
    return None


def _lite_filename_groups(
    paths: list[Path],
    *,
    rule: str,
    parse: Callable[[str], tuple[str, int] | None],
    require_positive_index: bool = False,
) -> list[_LiteSerialGroup]:
    by_base: dict[str, list[tuple[int, Path]]] = defaultdict(list)
    for path in paths:
        parsed = parse(path.stem)
        if parsed is None:
            continue
        base, index = parsed
        by_base[base].append((index, path))
    groups: list[_LiteSerialGroup] = []
    for base, entries in by_base.items():
        if require_positive_index and not any(idx > 0 for idx, _path in entries):
            continue
        if len(entries) < _LITE_MIN_GROUP:
            continue
        ordered = tuple(
            path for _idx, path in sorted(entries, key=lambda e: (e[0], e[1].name))
        )
        groups.append(
            _LiteSerialGroup(base_key=base, ordered_paths=ordered, matched_rule=rule)
        )
    return groups


def _lite_voice_note_groups(paths: list[Path]) -> list[_LiteSerialGroup]:
    parsed: list[tuple[str, datetime | None, int | None, Path]] = []
    for path in paths:
        result = _lite_parse_voice_note(path.stem)
        if result is None:
            continue
        family, recorded_at, sequence = result
        parsed.append((family, recorded_at, sequence, path))
    if len(parsed) < _LITE_MIN_GROUP:
        return []
    parsed.sort(
        key=lambda item: (
            item[0].lower(),
            item[1] is None,
            item[1] or datetime.min,
            item[2] if item[2] is not None else -1,
            item[3].name,
        )
    )
    groups: list[_LiteSerialGroup] = []
    cluster: list[tuple[datetime | None, int | None, Path]] = []
    cluster_family = ""

    def flush() -> None:
        if len(cluster) < _LITE_MIN_GROUP:
            cluster.clear()
            return
        first_dt, first_seq, _first = cluster[0]
        if first_dt is None:
            base_key = f"{cluster_family} {first_seq}"
        elif first_seq is not None:
            base_key = f"{cluster_family} {first_dt:%Y-%m-%d}"
        else:
            base_key = f"{cluster_family} {first_dt:%Y-%m-%d %H:%M:%S}"
        groups.append(
            _LiteSerialGroup(
                base_key=base_key,
                ordered_paths=tuple(path for _dt, _seq, path in cluster),
                matched_rule="voice_note_run",
            )
        )
        cluster.clear()

    def breaks(
        family: str, recorded_at: datetime | None, sequence: int | None
    ) -> bool:
        if not cluster:
            return False
        if family != cluster_family:
            return True
        prev_dt, prev_seq, _prev = cluster[-1]
        if recorded_at is None and prev_dt is None:
            if sequence is None or prev_seq is None:
                return True
            return (sequence - prev_seq - 1) > _LITE_MAX_INDEX_GAP
        if recorded_at is None or prev_dt is None:
            return True
        if sequence is not None and prev_seq is not None:
            if recorded_at.date() != prev_dt.date():
                return True
            return (sequence - prev_seq - 1) > _LITE_MAX_INDEX_GAP
        return (recorded_at - prev_dt).total_seconds() > _LITE_VOICE_GAP_SECONDS

    for family, recorded_at, sequence, path in parsed:
        if breaks(family, recorded_at, sequence):
            flush()
        if not cluster:
            cluster_family = family
        cluster.append((recorded_at, sequence, path))
    flush()
    return groups


def _lite_choose_groups(candidates: list[_LiteSerialGroup]) -> list[_LiteSerialGroup]:
    priority_len = len(_LITE_RULE_PRIORITY)
    ranked = sorted(
        candidates,
        key=lambda g: (
            -(
                priority_len - _LITE_RULE_PRIORITY.index(g.matched_rule)
                if g.matched_rule in _LITE_RULE_PRIORITY
                else 0
            ),
            g.base_key,
        ),
    )
    assigned: set[Path] = set()
    chosen: list[_LiteSerialGroup] = []
    for group in ranked:
        member_paths = set(group.ordered_paths)
        if member_paths & assigned:
            continue
        chosen.append(group)
        assigned.update(member_paths)
    chosen.sort(key=lambda g: (g.base_key, str(g.ordered_paths[0])))
    return chosen


def lite_detect_serial_groups(paths: Sequence[Path]) -> list[_LiteSerialGroup]:
    """Filename + common voice-note serial groups (standalone fallback)."""
    normalized = _lite_normalize_paths(paths)
    if len(normalized) < _LITE_MIN_GROUP:
        return []
    candidates: list[_LiteSerialGroup] = []
    candidates.extend(
        _lite_filename_groups(
            normalized, rule="timestamp_suffix", parse=_lite_parse_timestamp
        )
    )
    candidates.extend(
        _lite_filename_groups(normalized, rule="part_suffix", parse=_lite_parse_part)
    )
    candidates.extend(_lite_voice_note_groups(normalized))
    candidates.extend(
        _lite_filename_groups(
            normalized, rule="numeric_index", parse=_lite_parse_numeric
        )
    )
    candidates.extend(
        _lite_filename_groups(
            normalized,
            rule="duplicate_suffix",
            parse=_lite_parse_duplicate,
            require_positive_index=True,
        )
    )
    return _lite_choose_groups(candidates)


def _ensure_transcriptx_src_on_path() -> None:
    repo_root = find_repo_root()
    if repo_root is None:
        return
    src = repo_root / "src"
    if src.is_dir():
        src_str = str(src)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)


def detect_serial_groups_via_transcriptx(
    paths: Sequence[Path],
) -> list[_LiteSerialGroup] | None:
    """Use Auto-merge detection when TranscriptX is importable."""
    _ensure_transcriptx_src_on_path()
    try:
        from transcriptx.core.audio.serial_groups import (
            detect_merge_groups,
            detect_serial_audio_groups,
        )
    except ImportError:
        return None
    try:
        from transcriptx.core.audio.merge_profiles import load_merge_source_profiles

        raw_groups = detect_merge_groups(paths, profiles=load_merge_source_profiles())
    except Exception:
        try:
            raw_groups = detect_serial_audio_groups(paths)
        except Exception:
            return None
    return [
        _LiteSerialGroup(
            base_key=group.base_key,
            ordered_paths=tuple(group.ordered_paths),
            matched_rule=group.matched_rule,
        )
        for group in raw_groups
    ]


def _exclude_permanently_dismissed_serial_groups(
    groups: Sequence[_LiteSerialGroup],
) -> list[_LiteSerialGroup]:
    """Drop groups the user marked Don't suggest again on Auto-merge."""
    try:
        from transcriptx.core.audio.merge_dismissals import (
            filter_permanently_dismissed,
        )
    except ImportError:
        return list(groups)
    try:
        return list(filter_permanently_dismissed(groups))
    except Exception:
        return list(groups)


def serial_skip_reasons(
    paths: Sequence[Path],
) -> tuple[dict[Path, str], str]:
    """Map original MP3 paths in serial groups to a reason string.

    Returns (reasons, detector) where detector is ``auto-merge`` or ``lite``.
    """
    original_by_resolved: dict[Path, Path] = {}
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        original_by_resolved.setdefault(resolved, path)

    detector = "auto-merge"
    groups = detect_serial_groups_via_transcriptx(paths)
    if groups is None:
        detector = "lite"
        groups = lite_detect_serial_groups(paths)
    groups = _exclude_permanently_dismissed_serial_groups(groups)

    reasons: dict[Path, str] = {}
    for group in groups:
        n = len(group.ordered_paths)
        label = group.matched_rule.replace("_", " ")
        reason = f"{label} · {group.base_key} ({n} parts)"
        for member in group.ordered_paths:
            original = original_by_resolved.get(member, member)
            reasons[original] = reason
            reasons.setdefault(member, reason)
    return reasons, detector


def _exact_transcript_names(stem: str) -> list[str]:
    return [f"{stem}{suffix}" for suffix in _EXACT_SUFFIXES]


_DISAMBIG_STEM_RE = re.compile(r"^(.+) \((\d+)\)$")


def skip_search_dirs(transcripts_dir: Path, *, source: Path | None = None) -> list[Path]:
    """Folders to scan for already-done JSON without writing into them.

    Always includes ``transcripts_dir`` (the write target, typically originals/).
    When that folder is named ``originals``, also include its parent so canonical
    library JSON from a prior import counts as done. Source is included so a
    sidecar next to the MP3 is not re-transcribed.
    """
    dirs: list[Path] = []
    seen: set[str] = set()

    def add(path: Path | None) -> None:
        if path is None:
            return
        key = str(path.expanduser())
        if key in seen:
            return
        seen.add(key)
        dirs.append(path)

    add(transcripts_dir)
    if transcripts_dir.name == "originals":
        add(transcripts_dir.parent)
    add(source)
    return dirs


def _is_disambiguated_archive_stem(file_stem: str, audio_stem: str) -> bool:
    """True for ``foo (1)`` when the audio stem is ``foo`` (originals archive names)."""
    match = _DISAMBIG_STEM_RE.fullmatch(file_stem)
    if match is None:
        return False
    return match.group(1).casefold() == audio_stem.casefold()


def find_existing_transcript(
    transcripts_dir: Path, stem: str, *, fuzzy: bool = False
) -> Path | None:
    """Return path to an existing transcript JSON for stem, or None."""
    if not transcripts_dir.is_dir():
        return None

    for name in _exact_transcript_names(stem):
        candidate = transcripts_dir / name
        if candidate.is_file():
            return candidate

    wanted_exact = {name.lower() for name in _exact_transcript_names(stem)}
    stem_l = stem.lower()
    fuzzy_hit: Path | None = None
    for path in transcripts_dir.iterdir():
        if not path.is_file() or path.suffix.lower() != ".json":
            continue
        if path.name.lower() in wanted_exact:
            return path
        file_stem = path.stem
        if _is_disambiguated_archive_stem(file_stem, stem):
            return path
        if fuzzy and fuzzy_hit is None:
            file_stem_l = file_stem.lower()
            for sep in ("-", "_", "."):
                prefix = f"{stem_l}{sep}"
                if file_stem_l.startswith(prefix) and len(file_stem_l) > len(prefix):
                    fuzzy_hit = path
                    break
    return fuzzy_hit


def find_existing_transcript_in_dirs(
    dirs: Sequence[Path], stem: str, *, fuzzy: bool = False
) -> Path | None:
    for folder in dirs:
        found = find_existing_transcript(folder, stem, fuzzy=fuzzy)
        if found is not None:
            return found
    return None


def redact(text: str, secrets: Sequence[str]) -> str:
    result = text
    for secret in secrets:
        if secret:
            result = result.replace(secret, "***REDACTED***")
    return result


def probe_output_format_support(whispermlx: Path) -> bool:
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
    help_text = (proc.stdout or "") + (proc.stderr or "")
    return "output_format" in help_text or re.search(r"\s-f\b", help_text) is not None


def build_command(
    cfg: EffectiveConfig,
    mp3_path: Path,
    temp_dir: Path,
    *,
    output_format_supported: bool,
    hf_token: str | None,
) -> list[str]:
    cmd = [
        str(cfg.whispermlx),
        str(mp3_path),
        "--output_dir",
        str(temp_dir),
        "--language",
        cfg.language,
        "--model",
        cfg.model,
    ]
    if cfg.use_output_format_flag and output_format_supported:
        cmd.extend(["-f", cfg.output_format])
    if cfg.diarize:
        cmd.append("--diarize")
    if cfg.pass_hf_token_arg and hf_token:
        cmd.extend(["--hf_token", hf_token])
    cmd.extend(cfg.extra_whisper_args)
    return cmd


def format_command(cmd: Sequence[str], secrets: Sequence[str]) -> str:
    return redact(shlex.join(cmd), secrets)


def run_whispermlx(
    cmd: Sequence[str],
    proc_env: dict[str, str],
    *,
    quiet: bool,
) -> tuple[int, str]:
    """Run whispermlx. Returns (returncode, stderr text when quiet else empty)."""
    if quiet:
        proc = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            env=proc_env,
            check=False,
        )
        return proc.returncode, proc.stderr or ""
    proc = subprocess.run(list(cmd), env=proc_env, check=False)
    return proc.returncode, ""


def discover_json_candidate(temp_dir: Path, stem: str, run_start: float) -> Path | None:
    exact = temp_dir / f"{stem}.json"
    if exact.is_file():
        return exact

    candidates = [
        p
        for p in temp_dir.rglob("*.json")
        if p.is_file() and p.stat().st_mtime >= run_start - 0.5
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def validate_json_file(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "JSON file does not exist"
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"cannot read JSON: {exc}"
    if not content.strip():
        return False, "JSON is empty"
    try:
        json.loads(content)
    except json.JSONDecodeError as exc:
        return False, f"JSON invalid: {exc}"
    return True, ""


def _make_temp_dir(transcripts_dir: Path, stem: str) -> Path:
    base = transcripts_dir / ".whispermlx-missing" / "tmp"
    base.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^\w.\-]+", "_", stem) or "audio"
    created = tempfile.mkdtemp(prefix=f"{safe_stem}.", dir=base)
    return Path(created)


def _record_failure(
    mp3_name: str,
    reason: str,
    temp_dir: Path | None,
    *,
    clean_failed: bool,
    exit_code: int | None = None,
) -> FailedItem:
    kept: Path | None = temp_dir
    if clean_failed and temp_dir is not None and temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
        kept = None
        reason = f"{reason}; temp removed"
    return FailedItem(
        mp3_name=mp3_name,
        reason=reason,
        exit_code=exit_code,
        temp_dir=kept,
    )


def _cleanup_temp_dir(temp_dir: Path, *, keep: bool, clean_non_json: bool) -> None:
    if keep:
        return
    if not temp_dir.exists():
        return
    if clean_non_json:
        for item in temp_dir.rglob("*"):
            if item.is_file() and item.suffix.lower() != ".json":
                item.unlink(missing_ok=True)
    shutil.rmtree(temp_dir, ignore_errors=True)


def _build_proc_env(env_file: Path) -> tuple[dict[str, str], str | None]:
    proc_env = os.environ.copy()
    file_env = parse_env_file(env_file)
    proc_env.update(file_env)
    token = proc_env.get("HF_TOKEN") or None
    return proc_env, token


def validate_config_shape(cfg: EffectiveConfig) -> None:
    if not str(cfg.env_file).strip():
        raise SystemExit("ERROR: env_file is required")
    if not str(cfg.whispermlx).strip():
        raise SystemExit("ERROR: whispermlx path is required")
    if not cfg.model:
        raise SystemExit("ERROR: model is required")
    if not cfg.language:
        raise SystemExit("ERROR: language is required")


def warn_missing_paths(cfg: EffectiveConfig) -> None:
    if cfg.source is None:
        print("WARNING: source folder not set", file=sys.stderr)
    elif not cfg.source.exists():
        print(f"WARNING: source folder does not exist: {cfg.source}", file=sys.stderr)
    if cfg.transcripts is None:
        print("WARNING: transcripts folder not set", file=sys.stderr)
    elif not cfg.transcripts.exists():
        print(
            f"WARNING: transcripts folder does not exist: {cfg.transcripts}",
            file=sys.stderr,
        )
    if not cfg.env_file.is_file():
        print(f"WARNING: env file does not exist: {cfg.env_file}", file=sys.stderr)
    if not cfg.whispermlx.is_file():
        print(
            f"WARNING: whispermlx binary does not exist: {cfg.whispermlx}",
            file=sys.stderr,
        )
    elif not os.access(cfg.whispermlx, os.X_OK):
        print(
            f"WARNING: whispermlx binary is not executable: {cfg.whispermlx}",
            file=sys.stderr,
        )


def looks_like_managed_library_root(path: Path) -> bool:
    """True when *path* is the managed transcripts library root (not originals/)."""
    resolved = path.expanduser()
    if resolved.name == "originals":
        return False
    markers = ("metadata", "originals", "imports")
    try:
        return any((resolved / name).is_dir() for name in markers)
    except OSError:
        return False


def validate_for_dry_run(cfg: EffectiveConfig) -> tuple[dict[str, str], str | None]:
    """Lightweight validation for --dry-run (no HF_TOKEN/env-file requirements)."""
    validate_config_shape(cfg)

    if cfg.source is None:
        raise SystemExit("ERROR: --source is required (or save it in config)")
    if not cfg.source.is_dir():
        raise SystemExit(f"ERROR: source folder does not exist: {cfg.source}")

    if cfg.transcripts is None:
        raise SystemExit("ERROR: --transcripts is required (or save it in config)")
    if looks_like_managed_library_root(cfg.transcripts):
        raise SystemExit(
            "ERROR: --transcripts must be the originals/ folder "
            "(e.g. …/transcripts/originals), not the managed library root that "
            "contains metadata/ or imports/. Point JSON/CLI config at originals/, "
            "or set TRANSCRIPTX_TRANSCRIPTS_DIR to the library base (script appends "
            "/originals)."
        )

    if not cfg.whispermlx.is_file():
        print(
            f"WARNING: whispermlx binary not found: {cfg.whispermlx}",
            file=sys.stderr,
        )
    elif not os.access(cfg.whispermlx, os.X_OK):
        print(
            f"WARNING: whispermlx binary is not executable: {cfg.whispermlx}",
            file=sys.stderr,
        )

    proc_env = os.environ.copy()
    hf_token: str | None = None
    if cfg.env_file.is_file():
        proc_env.update(parse_env_file(cfg.env_file))
        hf_token = proc_env.get("HF_TOKEN") or None
    elif cfg.diarize:
        print(
            "WARNING: env file not found; dry-run command preview may omit HF_TOKEN",
            file=sys.stderr,
        )

    return proc_env, hf_token


def validate_for_processing(cfg: EffectiveConfig) -> tuple[dict[str, str], str | None]:
    validate_config_shape(cfg)

    if cfg.source is None:
        raise SystemExit("ERROR: --source is required (or save it in config)")
    if not cfg.source.is_dir():
        raise SystemExit(f"ERROR: source folder does not exist: {cfg.source}")

    if cfg.transcripts is None:
        raise SystemExit("ERROR: --transcripts is required (or save it in config)")
    if looks_like_managed_library_root(cfg.transcripts):
        raise SystemExit(
            "ERROR: --transcripts must be the originals/ folder "
            "(e.g. …/transcripts/originals), not the managed library root that "
            "contains metadata/ or imports/. Point JSON/CLI config at originals/, "
            "or set TRANSCRIPTX_TRANSCRIPTS_DIR to the library base (script appends "
            "/originals)."
        )
    if not cfg.transcripts.exists():
        cfg.transcripts.mkdir(parents=True, exist_ok=True)
        print(f"Created transcripts folder: {cfg.transcripts}")

    if not cfg.env_file.is_file():
        raise SystemExit(f"ERROR: env file does not exist: {cfg.env_file}")

    if not cfg.whispermlx.is_file():
        raise SystemExit(f"ERROR: whispermlx binary not found: {cfg.whispermlx}")
    if not os.access(cfg.whispermlx, os.X_OK):
        raise SystemExit(f"ERROR: whispermlx is not executable: {cfg.whispermlx}")

    proc_env, token = _build_proc_env(cfg.env_file)
    if cfg.diarize and not token:
        raise SystemExit("ERROR: HF_TOKEN required for diarization (set in env file)")

    if shutil.which("ffmpeg") is None:
        print("WARNING: ffmpeg not found on PATH; whispermlx may fail", file=sys.stderr)

    return proc_env, token


def process_one(
    cfg: EffectiveConfig,
    mp3_path: Path,
    *,
    force: bool,
    proc_env: dict[str, str],
    hf_token: str | None,
    output_format_supported: bool,
    keep_temp: bool,
    clean_failed: bool,
    dry_run: bool,
    dry_run_verbose: bool = True,
    quiet: bool = False,
) -> tuple[str, FailedItem | None]:
    """
    Process a single MP3. Returns ('skipped'|'processed'|'failed'|'dry_run', FailedItem|None).
    """
    stem = mp3_path.stem
    secrets = [s for s in [hf_token] if s]

    if dry_run:
        temp_placeholder = (
            cfg.transcripts / ".whispermlx-missing" / "tmp" / f"{stem}.<mkdtemp>"
        )
        if dry_run_verbose:
            cmd = build_command(
                cfg,
                mp3_path,
                temp_placeholder,
                output_format_supported=output_format_supported,
                hf_token=hf_token,
            )
            print(f"Would process: {mp3_path.name}")
            print(f"  command: {format_command(cmd, secrets)}")
        return "dry_run", None

    assert cfg.transcripts is not None
    temp_dir = _make_temp_dir(cfg.transcripts, stem)
    run_start = time.time()
    cmd = build_command(
        cfg,
        mp3_path,
        temp_dir,
        output_format_supported=output_format_supported,
        hf_token=hf_token,
    )

    print(f"Processing: {mp3_path.name}")
    if not quiet:
        print("---")
    try:
        returncode, stderr_text = run_whispermlx(cmd, proc_env, quiet=quiet)
    except OSError as exc:
        return "failed", _record_failure(
            mp3_path.name,
            redact(str(exc), secrets),
            temp_dir if temp_dir.exists() else None,
            clean_failed=clean_failed,
        )

    if returncode != 0:
        if quiet:
            stderr_tail = redact(stderr_text[-2000:], secrets)
            if stderr_tail.strip():
                print(f"  stderr: {stderr_tail[-500:]}", file=sys.stderr)
        return "failed", _record_failure(
            mp3_path.name,
            f"whispermlx exit {returncode}",
            temp_dir,
            clean_failed=clean_failed,
            exit_code=returncode,
        )

    candidate = discover_json_candidate(temp_dir, stem, run_start)
    if candidate is None:
        return "failed", _record_failure(
            mp3_path.name,
            "no JSON found in temp output",
            temp_dir,
            clean_failed=clean_failed,
            exit_code=0,
        )

    valid, err = validate_json_file(candidate)
    if not valid:
        return "failed", _record_failure(
            mp3_path.name,
            err,
            temp_dir,
            clean_failed=clean_failed,
            exit_code=0,
        )

    target = cfg.transcripts / f"{stem}.json"
    if target.exists() and not force:
        return "failed", _record_failure(
            mp3_path.name,
            f"target exists without --force: {target.name}",
            temp_dir,
            clean_failed=clean_failed,
        )

    extra_json = [
        p
        for p in temp_dir.rglob("*.json")
        if p.is_file() and p.resolve() != candidate.resolve()
    ]
    if extra_json:
        names = ", ".join(p.name for p in extra_json)
        print(
            f"  WARNING: extra JSON in temp ({names}); promoting {candidate.name} only"
        )

    try:
        os.replace(candidate, target)
    except OSError as exc:
        return "failed", _record_failure(
            mp3_path.name,
            f"promotion failed: {exc}",
            temp_dir,
            clean_failed=clean_failed,
        )

    _cleanup_temp_dir(temp_dir, keep=keep_temp, clean_non_json=cfg.clean_non_json)
    print(f"  wrote: {target}")
    return "processed", None


def _print_limited_items(
    label: str,
    items: Sequence[str],
    *,
    limit: int = DRY_RUN_LIST_LIMIT,
) -> None:
    if not items:
        return
    shown = min(len(items), limit)
    print(f"  {label} (first {shown} of {len(items)}):")
    for item in items[:limit]:
        print(f"    - {item}")
    if len(items) > limit:
        print(f"    ... and {len(items) - limit} more")


def print_summary(
    stats: RunStats, transcripts_dir: Path | None, *, dry_run: bool = False
) -> None:
    print()
    print("Summary")
    if dry_run:
        print(f"  would process: {stats.would_process}")
        _print_limited_items("would process", stats.would_process_names)
        print(f"  skipped:   {stats.skipped}")
        if stats.skipped_serial:
            print(f"  skipped likely serial: {stats.skipped_serial}")
            _print_limited_items("skipped likely serial", stats.skipped_serial_names)
    else:
        print(f"  processed: {stats.processed}")
        print(f"  skipped:   {stats.skipped}")
        if stats.skipped_serial:
            print(f"  skipped likely serial: {stats.skipped_serial}")
            _print_limited_items("skipped likely serial", stats.skipped_serial_names)
    print(f"  failed:    {stats.failed}")
    if transcripts_dir is not None:
        print(f"  transcripts: {transcripts_dir}")
    if stats.failed_items:
        print("  failed items:")
        for item in stats.failed_items:
            parts = [item.mp3_name, f"({item.reason}"]
            if item.exit_code is not None and "exit" not in item.reason:
                parts.append(f"; exit {item.exit_code}")
            if item.temp_dir is not None:
                parts.append(f"; temp: {item.temp_dir}")
            parts.append(")")
            print(f"    - {' '.join(parts)}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = resolve_config_path(args)
    try:
        cfg = resolve_config(args, config_path=config_path)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.show_config:
        print_effective_config(cfg)
        print(f"Config file: {config_path}", file=sys.stderr)
        return 0

    if args.save_config:
        will_process = _processing_will_run(args, cfg, save_config_only=True)
        if will_process:
            validate_config_shape(cfg)
        else:
            warn_missing_paths(cfg)
        save_config(cfg, config_path)
        print(f"Saved config: {config_path}")
        if not will_process:
            return 0

    # Processing or dry-run
    if args.dry_run or _processing_will_run(args, cfg):
        try:
            if args.dry_run:
                proc_env, hf_token = validate_for_dry_run(cfg)
            else:
                proc_env, hf_token = validate_for_processing(cfg)
        except SystemExit as exc:
            print(str(exc), file=sys.stderr)
            return 2

        output_format_supported = False
        if cfg.whispermlx.is_file() and os.access(cfg.whispermlx, os.X_OK):
            output_format_supported = probe_output_format_support(cfg.whispermlx)
        elif cfg.use_output_format_flag:
            print(
                "WARNING: whispermlx binary unavailable; cannot probe output_format/-f",
                file=sys.stderr,
            )
        print(
            describe_output_format_note(
                cfg, output_format_supported=output_format_supported
            ),
            file=sys.stderr,
        )
        if cfg.use_output_format_flag and not output_format_supported:
            print(
                "WARNING: whispermlx --help does not show output_format/-f; "
                "omitting format flag",
                file=sys.stderr,
            )

        assert cfg.source is not None
        mp3s = discover_mp3s(cfg.source)
        if not mp3s:
            print(f"No MP3 files found in {cfg.source}")
            print_summary(RunStats(), cfg.transcripts, dry_run=args.dry_run)
            return 0

        stats = RunStats()
        assert cfg.transcripts is not None
        skip_dirs = skip_search_dirs(cfg.transcripts, source=cfg.source)
        serial_reasons: dict[Path, str] = {}
        if cfg.skip_serial:
            serial_reasons, detector = serial_skip_reasons(mp3s)
            print(
                f"Note: --skip-serial is on ({detector} detector); "
                "MP3s that look like Auto-merge groups will not be transcribed.",
                file=sys.stderr,
            )
        for mp3_path in mp3s:
            stem = mp3_path.stem
            serial_reason = serial_reasons.get(mp3_path)
            if serial_reason is None:
                try:
                    serial_reason = serial_reasons.get(mp3_path.resolve())
                except OSError:
                    serial_reason = None
            if serial_reason is not None:
                stats.skipped += 1
                stats.skipped_serial += 1
                label = f"{mp3_path.name}  [{serial_reason}]"
                stats.skipped_serial_names.append(label)
                print(f"Skipping (likely serial, merge later): {label}")
                continue
            existing = find_existing_transcript_in_dirs(
                skip_dirs,
                stem,
                fuzzy=cfg.fuzzy_json_match,
            )
            if existing is not None and not args.force:
                stats.skipped += 1
                if not args.dry_run:
                    shown = (
                        existing.name
                        if existing.parent == cfg.transcripts
                        else str(existing)
                    )
                    print(f"Skipping (JSON exists): {mp3_path.name} -> {shown}")
                continue

            outcome, failed = process_one(
                cfg,
                mp3_path,
                force=args.force,
                proc_env=proc_env,
                hf_token=hf_token,
                output_format_supported=output_format_supported,
                keep_temp=args.keep_temp,
                clean_failed=args.clean_failed,
                dry_run=args.dry_run,
                dry_run_verbose=len(stats.would_process_names) < DRY_RUN_LIST_LIMIT,
                quiet=not cfg.follow_output,
            )
            if outcome == "processed":
                stats.processed += 1
            elif outcome == "dry_run":
                stats.would_process += 1
                stats.would_process_names.append(mp3_path.name)
            elif outcome == "failed" and failed is not None:
                stats.failed += 1
                stats.failed_items.append(failed)

        print_summary(stats, cfg.transcripts, dry_run=args.dry_run)
        return 1 if stats.failed > 0 else 0

    print(
        "Nothing to do. Set paths via CLI, .transcriptx/whispermlx-missing.json, "
        "or TRANSCRIPTX_* env; or use --show-config / --save-config.",
        file=sys.stderr,
    )
    return 2


def _has_meaningful_paths(provenance: ConfigProvenance) -> bool:
    return (
        provenance.source in _MEANINGFUL_PATH_SOURCES
        and provenance.transcripts in _MEANINGFUL_PATH_SOURCES
    )


def _processing_will_run(
    args: argparse.Namespace,
    cfg: EffectiveConfig,
    *,
    save_config_only: bool = False,
) -> bool:
    provenance = cfg.provenance
    if not _has_meaningful_paths(provenance):
        return False

    if args.dry_run:
        return True

    if save_config_only:
        cli_paths = args.source is not None or args.transcripts is not None
        json_paths = provenance.source == "json" and provenance.transcripts == "json"
        return cli_paths or json_paths

    return True


if __name__ == "__main__":
    raise SystemExit(main())
