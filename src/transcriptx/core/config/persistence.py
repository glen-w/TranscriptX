"""Config file persistence utilities."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional
import copy
import hashlib
import json
import os
import tempfile

from transcriptx.core.errors.coded import CodedError
from transcriptx.core.utils.file_lock import FileLock, LockAcquisitionError
from transcriptx.core.utils.paths import CONFIG_DIR

CONFIG_SCHEMA_VERSION = 1
CONFIG_DRAFTS_DIR = CONFIG_DIR / "drafts"
CONFIG_LOCK_TIMEOUT_SECONDS = 5


class ConfigLockTimeoutError(CodedError):
    """Could not acquire project config lock within timeout."""

    def __init__(
        self,
        message: str = "Could not acquire project config lock",
        *,
        error_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            error_code="CONFIG_LOCK_TIMEOUT",
            error_context=error_context,
        )


class ConfigCorruptError(CodedError):
    """Project config unreadable or invalid on load."""

    def __init__(
        self,
        message: str = "Project config unreadable or invalid",
        *,
        error_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            error_code="CONFIG_CORRUPT",
            error_context=error_context,
        )


@contextmanager
def config_write_lock(path: Path):
    """Exclusive lock for project-config writers (FileLock, 5s timeout)."""
    try:
        with FileLock(path, timeout=int(CONFIG_LOCK_TIMEOUT_SECONDS)):
            yield
    except LockAcquisitionError as exc:
        raise ConfigLockTimeoutError(
            f"Could not acquire config lock for {path}",
            error_context={"path": str(path)},
        ) from exc


@contextmanager
def config_read_lock(path: Path):
    """Shared-style read lock (same exclusive FileLock for simplicity)."""
    with config_write_lock(path):
        yield


def _wrap_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {"schema_version": CONFIG_SCHEMA_VERSION, "config": config_dict}


def _unwrap_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "config" in payload and isinstance(payload["config"], dict):
        return payload["config"]
    return payload


def save_config_atomic(config_dict: Dict[str, Any], target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _wrap_config(config_dict)
    temp_path: str | None = None
    with config_write_lock(target_path):
        try:
            fd, temp_path = tempfile.mkstemp(
                prefix=".config_tmp_",
                suffix=".json",
                dir=str(target_path.parent),
            )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, target_path)
        except Exception:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
            raise


def load_config_safe(config_path: Path) -> Optional[Dict[str, Any]]:
    if not config_path.exists():
        return None
    with config_read_lock(config_path):
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ConfigCorruptError(
                f"Config unreadable or invalid: {config_path}",
                error_context={"path": str(config_path), "error": str(exc)},
            ) from exc
    if not isinstance(payload, dict):
        raise ConfigCorruptError(
            f"Config root must be a JSON object: {config_path}",
            error_context={"path": str(config_path)},
        )
    return _unwrap_config(payload)


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
    # Compatibility: callers may pass a full on-disk payload
    # {"schema_version": ..., "config": {...}}. Persist the inner config
    # so load_project_config() always returns the nested settings map.
    save_config_atomic(_unwrap_config(config_dict), get_project_config_path())


def _set_nested(target: Dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cursor: Dict[str, Any] = target
    for part in parts[:-1]:
        nxt = cursor.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cursor[part] = nxt
        cursor = nxt
    cursor[parts[-1]] = value


def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_merge(dst[key], value)
        else:
            dst[key] = value


def patch_project_config_keys(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Patch project config keys under FileLock and return the new config dict.

    ``updates`` may be nested (e.g. ``{"analysis": {"llm_custom_qa": {...}}}``)
    or dotted keys mapped to values.
    """
    path = get_project_config_path()
    with config_write_lock(path):
        current: Dict[str, Any] = {}
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ConfigCorruptError(
                    f"Config unreadable or invalid: {path}",
                    error_context={"path": str(path), "error": str(exc)},
                ) from exc
            if not isinstance(payload, dict):
                raise ConfigCorruptError(
                    f"Config root must be a JSON object: {path}",
                    error_context={"path": str(path)},
                )
            unwrapped = _unwrap_config(payload)
            current = unwrapped if isinstance(unwrapped, dict) else {}
        merged = copy.deepcopy(current)
        if any("." in str(k) for k in updates):
            for key, value in updates.items():
                _set_nested(merged, str(key), value)
        else:
            for key, value in updates.items():
                if isinstance(value, dict) and isinstance(merged.get(key), dict):
                    _deep_merge(merged[key], value)
                else:
                    merged[key] = value
        wrapped = _wrap_config(merged)
        temp_path: str | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(
                prefix=".config_tmp_",
                suffix=".json",
                dir=str(path.parent),
            )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(wrapped, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except Exception:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
            raise
        return merged


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
    from transcriptx.core.utils.run_writer_locks import per_run_lock

    with per_run_lock(run_dir):
        save_config_atomic(config_dict, get_run_override_path(run_dir))


def load_run_effective(run_dir: Path) -> Optional[Dict[str, Any]]:
    return load_config_safe(get_run_effective_path(run_dir))


def save_run_effective(run_dir: Path, config_dict: Dict[str, Any]) -> None:
    from transcriptx.core.utils.run_writer_locks import per_run_lock

    with per_run_lock(run_dir):
        save_config_atomic(config_dict, get_run_effective_path(run_dir))


def compute_config_hash(config_dict: Dict[str, Any]) -> str:
    payload = json.dumps(
        config_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"
