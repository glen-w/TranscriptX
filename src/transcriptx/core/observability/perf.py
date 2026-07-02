"""Performance instrumentation primitives for load assessment."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from transcriptx.core.utils.logger import get_logger

_LOGGER = get_logger()
_LOCK = threading.RLock()
_WARNING_HANDLER_INSTALLED = False
_RUN_LOCAL = threading.local()
_CACHE_MISS_COUNTS: Counter[str] = Counter()


def _enabled() -> bool:
    return os.environ.get("TRANSCRIPTX_STREAMLIT_PERF", "1").lower() not in {
        "0",
        "false",
        "off",
        "no",
    }


def _output_path() -> Path:
    raw = os.environ.get("TRANSCRIPTX_STREAMLIT_PERF_PATH")
    if raw:
        return Path(raw)
    data_dir = os.environ.get("TRANSCRIPTX_DATA_DIR")
    if data_dir:
        return Path(data_dir) / "perf" / "streamlit_load_profile.jsonl"
    return Path.cwd() / "perf" / "streamlit_load_profile.jsonl"


def _safe_float_ms(start: float, end: float | None = None) -> float:
    stop = time.perf_counter() if end is None else end
    return round((stop - start) * 1000, 3)


def _normalize_path(path: str | os.PathLike[str]) -> str:
    try:
        return str(Path(path).expanduser().resolve())
    except (OSError, RuntimeError, ValueError):
        return str(path)


@dataclass
class FileReadRecord:
    count: int = 0
    sections: set[str] = field(default_factory=set)
    purposes: set[str] = field(default_factory=set)
    transcript_validation_reads: int = 0
    metadata_extraction_reads: int = 0
    segment_loading_reads: int = 0


@dataclass
class RunMetrics:
    run_id: str
    page: str | None
    scenario: str | None
    started_at: float
    started_at_epoch_ms: int
    section_totals_ms: Counter[str] = field(default_factory=Counter)
    section_events: list[dict[str, Any]] = field(default_factory=list)
    counts: Counter[str] = field(default_factory=Counter)
    cache_states: dict[str, str] = field(default_factory=dict)
    warning_count: int = 0
    file_reads: dict[str, FileReadRecord] = field(default_factory=dict)


def _current_run() -> RunMetrics | None:
    return getattr(_RUN_LOCAL, "metrics", None)


class _WarningCountingHandler(logging.Handler):
    def emit(self, record: Any) -> None:
        metrics = _current_run()
        if metrics is None:
            return
        levelno = getattr(record, "levelno", None)
        if isinstance(levelno, int) and levelno >= 30:
            metrics.warning_count += 1


def _ensure_warning_handler() -> None:
    global _WARNING_HANDLER_INSTALLED
    if _WARNING_HANDLER_INSTALLED or not _enabled():
        return
    logger = get_logger()
    handler = _WarningCountingHandler()
    # logging.Handler is not required for duck-typed handlers attached to logger
    logger.addHandler(handler)  # type: ignore[arg-type]
    _WARNING_HANDLER_INSTALLED = True


def _append_jsonl(payload: dict[str, Any]) -> None:
    if not _enabled():
        return
    path = _output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def reset_output() -> None:
    """Clear prior instrumentation output."""
    if not _enabled():
        return
    path = _output_path()
    if path.exists():
        path.unlink()


def start_run(*, page: str | None, scenario: str | None = None) -> str:
    """Start a new Streamlit rerun context."""
    if not _enabled():
        return "perf-disabled"
    _ensure_warning_handler()
    now = time.time()
    run_id = uuid.uuid4().hex[:12]
    _RUN_LOCAL.metrics = RunMetrics(
        run_id=run_id,
        page=page,
        scenario=scenario,
        started_at=time.perf_counter(),
        started_at_epoch_ms=int(now * 1000),
    )
    _append_jsonl(
        {
            "event": "run_started",
            "page": page,
            "run_id": run_id,
            "scenario": scenario,
            "started_at_epoch_ms": int(now * 1000),
        }
    )
    return run_id


def finish_run(*, notes: str | None = None) -> dict[str, Any] | None:
    """Finish the current run and emit a summary record."""
    metrics = _current_run()
    if metrics is None or not _enabled():
        return None
    total_wall_ms = _safe_float_ms(metrics.started_at)
    duplicate_paths = []
    duplicate_count = 0
    for path, record in sorted(metrics.file_reads.items()):
        if record.count <= 1:
            continue
        duplicate_count += 1
        duplicate_paths.append(
            {
                "count": record.count,
                "metadata_extraction_reads": record.metadata_extraction_reads,
                "path": path,
                "purposes": sorted(record.purposes),
                "sections": sorted(record.sections),
                "segment_loading_reads": record.segment_loading_reads,
                "transcript_validation_reads": record.transcript_validation_reads,
            }
        )
    summary = {
        "cache_hit_or_miss": dict(sorted(metrics.cache_states.items())),
        "counts": dict(sorted(metrics.counts.items())),
        "duplicate_file_reads": duplicate_paths,
        "event": "run_summary",
        "json_files_read_more_than_once": duplicate_count,
        "notes": notes,
        "page": metrics.page,
        "run_id": metrics.run_id,
        "scenario": metrics.scenario,
        "section_events": metrics.section_events,
        "section_totals_ms": dict(sorted(metrics.section_totals_ms.items())),
        "started_at_epoch_ms": metrics.started_at_epoch_ms,
        "total_wall_time_ms": total_wall_ms,
        "warnings_emitted": metrics.warning_count,
    }
    _append_jsonl(summary)
    delattr(_RUN_LOCAL, "metrics")
    return summary


def increment_count(name: str, amount: int = 1) -> None:
    metrics = _current_run()
    if metrics is None or not _enabled():
        return
    metrics.counts[name] += amount


def set_count(name: str, value: int) -> None:
    metrics = _current_run()
    if metrics is None or not _enabled():
        return
    metrics.counts[name] = value


def set_cache_state(name: str, state: str) -> None:
    metrics = _current_run()
    if metrics is None or not _enabled():
        return
    metrics.cache_states[name] = state


def mark_cache_miss(name: str) -> None:
    if not _enabled():
        return
    with _LOCK:
        _CACHE_MISS_COUNTS[name] += 1


def _cache_miss_count(name: str) -> int:
    with _LOCK:
        return _CACHE_MISS_COUNTS[name]


def record_file_read(
    path: str | os.PathLike[str],
    *,
    section: str,
    purpose: str,
    kind: str = "json",
) -> None:
    metrics = _current_run()
    if metrics is None or not _enabled() or kind != "json":
        return
    normalized = _normalize_path(path)
    record = metrics.file_reads.setdefault(normalized, FileReadRecord())
    record.count += 1
    record.sections.add(section)
    record.purposes.add(purpose)
    if purpose == "transcript_validation":
        record.transcript_validation_reads += 1
    elif purpose == "metadata_extraction":
        record.metadata_extraction_reads += 1
    elif purpose == "segment_loading":
        record.segment_loading_reads += 1
    metrics.counts["json_files_read"] += 1


def observe_transcript_path(path: str | os.PathLike[str]) -> None:
    metrics = _current_run()
    if metrics is None or not _enabled():
        return
    normalized = _normalize_path(path)
    seen = getattr(_RUN_LOCAL, "transcript_paths_seen", None)
    if seen is None:
        seen = set()
        _RUN_LOCAL.transcript_paths_seen = seen
    if normalized not in seen:
        seen.add(normalized)
        metrics.counts["transcript_json_files"] += 1


@contextmanager
def section(
    name: str,
    *,
    bucket: str,
    cache_state: str | None = None,
    counts: dict[str, int] | None = None,
    extra: dict[str, Any] | None = None,
) -> Iterator[None]:
    """Context manager for instrumented sections."""
    start = time.perf_counter()
    try:
        yield
    finally:
        metrics = _current_run()
        if metrics is None or not _enabled():
            return
        elapsed_ms = _safe_float_ms(start)
        metrics.section_totals_ms[bucket] += elapsed_ms
        event = {
            "bucket": bucket,
            "elapsed_ms": elapsed_ms,
            "run_id": metrics.run_id,
            "section": name,
            "warning_count": metrics.warning_count,
        }
        if cache_state is not None:
            event["cache_state"] = cache_state
        if counts:
            event["counts"] = counts
        if extra:
            event.update(extra)
        metrics.section_events.append(event)
        _append_jsonl({"event": "section", **event})


def instrument_cached_call(
    name: str,
    func: Any,
    *args: Any,
    bucket: str,
    counts: dict[str, int] | None = None,
    **kwargs: Any,
) -> Any:
    """Measure a cached call and infer hit/miss from cache-body execution."""
    before = _cache_miss_count(name)
    start = time.perf_counter()
    result = func(*args, **kwargs)
    after = _cache_miss_count(name)
    cache_state = "miss" if after > before else "hit"
    set_cache_state(name, cache_state)
    metrics = _current_run()
    if metrics is not None and _enabled():
        elapsed_ms = _safe_float_ms(start)
        metrics.section_totals_ms[bucket] += elapsed_ms
        event = {
            "bucket": bucket,
            "cache_state": cache_state,
            "counts": counts or {},
            "elapsed_ms": elapsed_ms,
            "run_id": metrics.run_id,
            "section": name,
            "warning_count": metrics.warning_count,
        }
        metrics.section_events.append(event)
        _append_jsonl({"event": "section", **event})
    return result


def maybe_set_scenario(scenario: str) -> None:
    metrics = _current_run()
    if metrics is None or not _enabled():
        return
    metrics.scenario = scenario


def section_total(name: str) -> float:
    metrics = _current_run()
    if metrics is None or not _enabled():
        return 0.0
    return float(metrics.section_totals_ms.get(name, 0.0))


def summarize_duplicate_reads() -> dict[str, dict[str, Any]]:
    metrics = _current_run()
    if metrics is None or not _enabled():
        return {}
    summary: dict[str, dict[str, Any]] = {}
    for path, record in metrics.file_reads.items():
        if record.count <= 1:
            continue
        summary[path] = {
            "count": record.count,
            "purposes": sorted(record.purposes),
            "sections": sorted(record.sections),
        }
    return summary


def record_elapsed_section(
    name: str,
    *,
    bucket: str,
    elapsed_ms: float,
    cache_state: str | None = None,
    counts: dict[str, int] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    metrics = _current_run()
    if metrics is None or not _enabled():
        return
    metrics.section_totals_ms[bucket] += elapsed_ms
    event = {
        "bucket": bucket,
        "elapsed_ms": round(elapsed_ms, 3),
        "run_id": metrics.run_id,
        "section": name,
        "warning_count": metrics.warning_count,
    }
    if cache_state is not None:
        event["cache_state"] = cache_state
    if counts:
        event["counts"] = counts
    if extra:
        event.update(extra)
    metrics.section_events.append(event)
    _append_jsonl({"event": "section", **event})


__all__ = [
    "FileReadRecord",
    "RunMetrics",
    "finish_run",
    "increment_count",
    "instrument_cached_call",
    "mark_cache_miss",
    "maybe_set_scenario",
    "observe_transcript_path",
    "record_elapsed_section",
    "record_file_read",
    "reset_output",
    "section",
    "section_total",
    "set_cache_state",
    "set_count",
    "start_run",
    "summarize_duplicate_reads",
]
