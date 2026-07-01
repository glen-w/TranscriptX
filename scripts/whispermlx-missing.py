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

Config file (default ~/.config/whispermlx-missing/config.json):
    --config /path/to/config.json
    or env WHISPERMLX_MISSING_CONFIG=/path/to/config.json

Dry run:
    whispermlx-missing --dry-run

Dry-run uses lightweight validation (source/transcripts paths and source folder only).
It does not require env file, HF_TOKEN, or a working whispermlx binary.

Already-processed detection (flat transcripts folder, JSON only):
    For MP3 stem ``foo``, skip if any of these exist in --transcripts:
    foo.json, foo.diarized.json, foo_diarized.json, foo.diarised.json, foo_diarised.json
    With --fuzzy-json-match, also match foo-<rest>.json, foo_<rest>.json, foo.<rest>.json
    (never matches foo2.json for stem foo).

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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

CONFIG_VERSION = 1
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "whispermlx-missing" / "config.json"
CONFIG_PATH = DEFAULT_CONFIG_PATH  # tests may monkeypatch
CONFIG_ENV_VAR = "WHISPERMLX_MISSING_CONFIG"

DEFAULT_ENV_FILE = Path("/Users/89298/Documents/transcriptx/whisperx.env")
DEFAULT_WHISPERMLX = Path("/Users/89298/venvs/whispermlx/bin/whispermlx")

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
    failed: int = 0
    would_process_names: list[str] = field(default_factory=list)
    failed_items: list[FailedItem] = field(default_factory=list)


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
    follow_output: bool


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
            "Config JSON path (default: ~/.config/whispermlx-missing/config.json). "
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


def default_config_dict() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "source": None,
        "transcripts": None,
        "env_file": str(DEFAULT_ENV_FILE),
        "whispermlx": str(DEFAULT_WHISPERMLX),
        "model": "large-v3",
        "language": "en",
        "diarize": True,
        "output_format": "json",
        "use_output_format_flag": True,
        "clean_non_json": True,
        "extra_whisper_args": [],
        "pass_hf_token_arg": False,
        "fuzzy_json_match": False,
        "follow_output": True,
    }


def resolve_config_path(args: argparse.Namespace) -> Path:
    if args.config is not None:
        return args.config.expanduser()
    env_val = os.environ.get(CONFIG_ENV_VAR, "").strip()
    if env_val:
        return Path(env_val).expanduser()
    return CONFIG_PATH


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or CONFIG_PATH
    if not config_path.is_file():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"ERROR: invalid config file {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: config file must be a JSON object: {config_path}")
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
        "follow_output": cfg.follow_output,
    }


def save_config(cfg: EffectiveConfig, path: Path | None = None) -> None:
    config_path = path or CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(config_to_dict(cfg), indent=2) + "\n"
    config_path.write_text(text, encoding="utf-8")
    os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)


def resolve_config(
    args: argparse.Namespace, *, config_path: Path | None = None
) -> EffectiveConfig:
    defaults = default_config_dict()
    active_config = config_path or resolve_config_path(args)
    file_cfg = load_config(active_config)

    merged: dict[str, Any] = {**defaults, **file_cfg}

    if args.source is not None:
        merged["source"] = str(args.source)
    if args.transcripts is not None:
        merged["transcripts"] = str(args.transcripts)
    if args.env_file is not None:
        merged["env_file"] = str(args.env_file)
    if args.whispermlx is not None:
        merged["whispermlx"] = str(args.whispermlx)
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
    if args.no_clean_non_json:
        merged["clean_non_json"] = False
    if args.quiet:
        merged["follow_output"] = False

    source = Path(merged["source"]).expanduser() if merged.get("source") else None
    transcripts = (
        Path(merged["transcripts"]).expanduser() if merged.get("transcripts") else None
    )

    extra = require_list_of_str(
        merged.get("extra_whisper_args") or [], "extra_whisper_args"
    )

    return EffectiveConfig(
        source=source,
        transcripts=transcripts,
        env_file=Path(require_str(merged["env_file"], "env_file")).expanduser(),
        whispermlx=Path(require_str(merged["whispermlx"], "whispermlx")).expanduser(),
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
        follow_output=require_bool(merged["follow_output"], "follow_output"),
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


def _exact_transcript_names(stem: str) -> list[str]:
    return [f"{stem}{suffix}" for suffix in _EXACT_SUFFIXES]


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

    if not fuzzy:
        return None

    for path in transcripts_dir.iterdir():
        if not path.is_file() or path.suffix.lower() != ".json":
            continue
        file_stem = path.stem
        for sep in ("-", "_", "."):
            prefix = f"{stem}{sep}"
            if file_stem.startswith(prefix) and len(file_stem) > len(prefix):
                return path
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
    if not cfg.env_file:
        raise SystemExit("ERROR: env_file is required")
    if not cfg.whispermlx:
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


def validate_for_dry_run(cfg: EffectiveConfig) -> tuple[dict[str, str], str | None]:
    """Lightweight validation for --dry-run (no HF_TOKEN/env-file requirements)."""
    validate_config_shape(cfg)

    if cfg.source is None:
        raise SystemExit("ERROR: --source is required (or save it in config)")
    if not cfg.source.is_dir():
        raise SystemExit(f"ERROR: source folder does not exist: {cfg.source}")

    if cfg.transcripts is None:
        raise SystemExit("ERROR: --transcripts is required (or save it in config)")

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
    else:
        print(f"  processed: {stats.processed}")
        print(f"  skipped:   {stats.skipped}")
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
        validate_config_shape(cfg)
        will_process = _processing_will_run(args, cfg)
        if not will_process:
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
        for mp3_path in mp3s:
            stem = mp3_path.stem
            existing = find_existing_transcript(
                cfg.transcripts,  # type: ignore[arg-type]
                stem,
                fuzzy=cfg.fuzzy_json_match,
            )
            if existing is not None and not args.force:
                stats.skipped += 1
                if not args.dry_run:
                    print(f"Skipping (JSON exists): {mp3_path.name} -> {existing.name}")
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
        "Nothing to do. Use --show-config, --save-config, or run with saved paths.",
        file=sys.stderr,
    )
    return 2


def _processing_will_run(args: argparse.Namespace, cfg: EffectiveConfig) -> bool:
    if args.dry_run:
        return True
    if args.source is not None or args.transcripts is not None:
        return True
    if cfg.source is not None and cfg.transcripts is not None:
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
