"""Load/write run_performance.json with typed load statuses."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from transcriptx.core.observability.run_performance.schema import (
    MAX_SIDECAR_BYTES,
    RUN_PERFORMANCE_SCHEMA_VERSION,
    RunPerformanceV1,
)
from transcriptx.core.utils.artifact_writer import write_json
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


class RunPerformanceLoadStatus(str, Enum):
    ok = "ok"
    missing = "missing"
    malformed = "malformed"
    unsupported_schema = "unsupported_schema"
    oversized = "oversized"
    io_error = "io_error"


@dataclass(frozen=True)
class RunPerformanceLoadResult:
    status: RunPerformanceLoadStatus
    payload: Optional[RunPerformanceV1] = None
    detail_code: Optional[str] = None


def run_performance_path(run_dir: str | Path) -> Path:
    return Path(run_dir) / ".transcriptx" / "run_performance.json"


def load_run_performance(
    run_dir: str | Path,
    *,
    expected_run_id: Optional[str] = None,
    expected_target_type: Optional[str] = None,
) -> RunPerformanceLoadResult:
    path = run_performance_path(run_dir)
    try:
        st = path.lstat()
    except FileNotFoundError:
        return RunPerformanceLoadResult(status=RunPerformanceLoadStatus.missing)
    except OSError:
        return RunPerformanceLoadResult(
            status=RunPerformanceLoadStatus.io_error, detail_code="lstat_failed"
        )

    if not path.is_file() or path.is_symlink():
        return RunPerformanceLoadResult(
            status=RunPerformanceLoadStatus.malformed, detail_code="not_regular_file"
        )
    if st.st_size > MAX_SIDECAR_BYTES:
        return RunPerformanceLoadResult(status=RunPerformanceLoadStatus.oversized)
    if st.st_size <= 0:
        return RunPerformanceLoadResult(
            status=RunPerformanceLoadStatus.malformed, detail_code="empty"
        )

    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError):
        return RunPerformanceLoadResult(
            status=RunPerformanceLoadStatus.io_error, detail_code="read_failed"
        )
    except json.JSONDecodeError:
        return RunPerformanceLoadResult(
            status=RunPerformanceLoadStatus.malformed, detail_code="invalid_json"
        )

    if not isinstance(data, dict):
        return RunPerformanceLoadResult(
            status=RunPerformanceLoadStatus.malformed, detail_code="not_object"
        )

    ver = data.get("schema_version")
    if ver != RUN_PERFORMANCE_SCHEMA_VERSION:
        return RunPerformanceLoadResult(
            status=RunPerformanceLoadStatus.unsupported_schema,
            detail_code=f"schema_version={ver!r}",
        )

    try:
        payload = RunPerformanceV1.model_validate(data)
    except Exception:
        return RunPerformanceLoadResult(
            status=RunPerformanceLoadStatus.malformed, detail_code="schema_validation"
        )

    if expected_run_id is not None and payload.run_id != expected_run_id:
        return RunPerformanceLoadResult(
            status=RunPerformanceLoadStatus.malformed, detail_code="run_id_mismatch"
        )
    if expected_target_type is not None and payload.target_type != expected_target_type:
        return RunPerformanceLoadResult(
            status=RunPerformanceLoadStatus.malformed,
            detail_code="target_type_mismatch",
        )

    return RunPerformanceLoadResult(status=RunPerformanceLoadStatus.ok, payload=payload)


def write_run_performance(run_dir: str | Path, snapshot: RunPerformanceV1) -> Path:
    """Atomic write with strict JSON (no NaN, no default=str)."""
    path = run_performance_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = snapshot.to_json_dict()
    # Re-validate serialisable form before write.
    RunPerformanceV1.model_validate(data)
    return write_json(
        path,
        data,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
        default=None,
    )
