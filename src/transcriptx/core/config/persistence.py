"""Config file persistence utilities."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional
import hashlib
import json

from transcriptx.core.utils.paths import PROJECT_ROOT

CONFIG_SCHEMA_VERSION = 1
CONFIG_DIR = Path(PROJECT_ROOT) / ".transcriptx"
CONFIG_DRAFTS_DIR = CONFIG_DIR / "drafts"


@contextmanager
def config_write_lock(path: Path):
    """Lock abstraction (no-op by default, can add portalocker/OS locks later)."""
    yield


@contextmanager
def config_read_lock(path: Path):
    """Read lock abstraction (no-op by default)."""
    yield


def _wrap_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {"schema_version": CONFIG_SCHEMA_VERSION, "config": config_dict}


def _unwrap_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "config" in payload and isinstance(payload["config"], dict):
        return payload["config"]
    return payload


def save_config_atomic(config_dict: Dict[str, Any], target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".tmp")
    payload = _wrap_config(config_dict)
    with config_write_lock(target_path):
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(target_path)


def load_config_safe(config_path: Path) -> Optional[Dict[str, Any]]:
    if not config_path.exists():
        return None
    with config_read_lock(config_path):
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    return _unwrap_config(payload) if isinstance(payload, dict) else None


def get_project_config_path() -> Path:
    return CONFIG_DIR / "config.json"


def get_draft_override_path() -> Path:
    return CONFIG_DRAFTS_DIR / "run_override.json"


def get_run_override_path(run_dir: Path) -> Path:
    return run_dir / ".transcriptx" / "run_config_override.json"


def get_run_effective_path(run_dir: Path) -> Path:
    return run_dir / ".transcriptx" / "run_config_effective.json"


def load_project_config() -> Optional[Dict[str, Any]]:
    return load_config_safe(get_project_config_path())


def save_project_config(config_dict: Dict[str, Any]) -> None:
    save_config_atomic(config_dict, get_project_config_path())


def load_draft_override() -> Optional[Dict[str, Any]]:
    return load_config_safe(get_draft_override_path())


def save_draft_override(config_dict: Dict[str, Any]) -> None:
    save_config_atomic(config_dict, get_draft_override_path())


def clear_draft_override() -> None:
    path = get_draft_override_path()
    if path.exists():
        path.unlink()


def load_run_override(run_dir: Path) -> Optional[Dict[str, Any]]:
    return load_config_safe(get_run_override_path(run_dir))


def save_run_override(run_dir: Path, config_dict: Dict[str, Any]) -> None:
    save_config_atomic(config_dict, get_run_override_path(run_dir))


def load_run_effective(run_dir: Path) -> Optional[Dict[str, Any]]:
    return load_config_safe(get_run_effective_path(run_dir))


def save_run_effective(run_dir: Path, config_dict: Dict[str, Any]) -> None:
    save_config_atomic(config_dict, get_run_effective_path(run_dir))


def compute_config_hash(config_dict: Dict[str, Any]) -> str:
    payload = json.dumps(config_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"
