"""Retained-run snapshot exporter (Prometheus textfile gauges).

Each export cycle rescans currently retained committed runs and regenerates
gauge / histogram-bucket snapshot metrics from scratch. Deleted run directories
disappear from the next snapshot. No mtime ingest state and no counters that
cannot shrink when inventory shrinks.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from transcriptx.core.observability.run_performance.inventory import (
    DEFAULT_MAX_COMMITTED_RUNS,
    CommittedRunRef,
    InventoryScanResult,
    scan_committed_runs,
)
from transcriptx.core.observability.run_performance.io import (
    RunPerformanceLoadStatus,
    load_run_performance,
)
from transcriptx.core.observability.run_performance.schema import (
    MAX_STRING_LEN,
    RunPerformanceV1,
)
from transcriptx.core.utils.artifact_writer import write_text
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import GROUP_OUTPUTS_DIR, OUTPUTS_DIR, STATE_DIR

logger = get_logger()

# Default wall / module duration histogram bucket upper bounds (seconds).
DEFAULT_DURATION_BUCKETS_S: Tuple[float, ...] = (
    1.0,
    5.0,
    15.0,
    30.0,
    60.0,
    120.0,
    300.0,
    600.0,
    1800.0,
    3600.0,
)

ALLOWED_MODES = frozenset({"quick", "full"})
ALLOWED_MODULE_STATUSES = frozenset(
    {"run", "succeeded", "failed", "blocked", "skipped", "not_requested", "unknown"}
)
BANNED_LABEL_KEYS = frozenset(
    {
        "run_id",
        "transcript_key",
        "path",
        "paths",
        "run_root",
        "fingerprint",
        "exception",
        "error",
        "message",
    }
)

_LABEL_RE = re.compile(r"[^a-zA-Z0-9_.:/-]+")
_MODEL_RE = re.compile(r"[^a-zA-Z0-9._:/-]+")

ENV_TEXTFILE_PATH = "TRANSCRIPTX_RUN_PERF_EXPORT_PATH"
ENV_MAX_RUNS = "TRANSCRIPTX_RUN_PERF_EXPORT_MAX_RUNS"


@dataclass(frozen=True)
class SnapshotExportConfig:
    outputs_dir: Path
    group_outputs_dir: Path
    textfile_path: Path
    max_runs: int = DEFAULT_MAX_COMMITTED_RUNS
    duration_buckets_s: Tuple[float, ...] = DEFAULT_DURATION_BUCKETS_S


@dataclass(frozen=True)
class MetricSample:
    name: str
    labels: Tuple[Tuple[str, str], ...]
    value: float
    help: str
    type: str = "gauge"


@dataclass
class RetainedRunSnapshot:
    """In-memory gauge / histogram-bucket snapshot for one scan."""

    samples: List[MetricSample] = field(default_factory=list)
    inventory: Optional[InventoryScanResult] = None
    runs_with_sidecar: int = 0
    runs_without_sidecar: int = 0


@dataclass(frozen=True)
class SnapshotExportResult:
    textfile_path: Path
    runs_exported: int
    candidates_seen: int
    scan_errors: int
    truncated: bool
    runs_with_sidecar: int
    runs_without_sidecar: int


def config_from_env(
    *,
    outputs_dir: Optional[Path] = None,
    group_outputs_dir: Optional[Path] = None,
    textfile_path: Optional[Path] = None,
    max_runs: Optional[int] = None,
) -> SnapshotExportConfig:
    """Build export config from PATHS defaults + optional env overrides."""
    out = Path(outputs_dir) if outputs_dir is not None else Path(OUTPUTS_DIR)
    if group_outputs_dir is not None:
        groups = Path(group_outputs_dir)
    elif outputs_dir is not None:
        # Keep group tree under the overridden outputs root.
        groups = out / "groups"
    else:
        groups = Path(GROUP_OUTPUTS_DIR)
    if textfile_path is not None:
        dest = Path(textfile_path)
    else:
        raw = os.environ.get(ENV_TEXTFILE_PATH)
        dest = (
            Path(raw).expanduser()
            if raw
            else Path(STATE_DIR) / "run_performance_snapshot.prom"
        )
    if max_runs is not None:
        cap = max_runs
    else:
        raw_cap = os.environ.get(ENV_MAX_RUNS)
        if raw_cap:
            try:
                cap = int(raw_cap.strip())
            except ValueError as exc:
                raise ValueError(f"{ENV_MAX_RUNS} must be an integer") from exc
        else:
            cap = DEFAULT_MAX_COMMITTED_RUNS
    return SnapshotExportConfig(
        outputs_dir=out,
        group_outputs_dir=groups,
        textfile_path=dest,
        max_runs=cap,
    )


def _norm_label_value(raw: Optional[str], *, fallback: str = "unknown") -> str:
    if raw is None:
        return fallback
    s = str(raw).strip().lower()
    if not s:
        return fallback
    s = _LABEL_RE.sub("_", s)
    return s[:MAX_STRING_LEN] or fallback


def _norm_mode(raw: Optional[str]) -> str:
    s = _norm_label_value(raw, fallback="unknown")
    if s in ALLOWED_MODES:
        return s
    if s == "unknown":
        return s
    return "other"


def _norm_module_status(raw: Optional[str]) -> str:
    s = _norm_label_value(raw, fallback="unknown")
    if s in ALLOWED_MODULE_STATUSES:
        return s
    return "unknown"


def _norm_model(raw: Optional[str]) -> str:
    if raw is None:
        return "unattributed"
    s = str(raw).strip().lower()
    if not s:
        return "unattributed"
    s = _MODEL_RE.sub("_", s)
    s = s[:64]
    return s or "unattributed"


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels_tuple(labels: Mapping[str, str]) -> Tuple[Tuple[str, str], ...]:
    for key in labels:
        if key in BANNED_LABEL_KEYS:
            raise ValueError(f"banned metric label key: {key}")
        if key.endswith("_id") and key not in {"module_id"}:
            raise ValueError(f"banned metric label key pattern: {key}")
    return tuple(sorted((k, str(v)) for k, v in labels.items()))


def _inc(
    counter: Dict[Tuple[Tuple[str, str], ...], float],
    labels: Mapping[str, str],
    amount: float = 1.0,
) -> None:
    key = _labels_tuple(labels)
    counter[key] += amount


def _bucket_edges(buckets: Sequence[float]) -> Tuple[float, ...]:
    edges = sorted({float(b) for b in buckets if float(b) >= 0})
    return tuple(edges)


def _observe_bucket(
    bucket_counts: Dict[Tuple[Tuple[str, str], ...], List[int]],
    *,
    base_labels: Mapping[str, str],
    value_s: float,
    edges: Sequence[float],
) -> None:
    """Accumulate non-cumulative per-edge counts; render as cumulative later."""
    key = _labels_tuple(base_labels)
    slots = bucket_counts.get(key)
    if slots is None:
        slots = [0] * (len(edges) + 1)  # last slot = +Inf
        bucket_counts[key] = slots
    placed = False
    for i, edge in enumerate(edges):
        if value_s <= edge:
            slots[i] += 1
            placed = True
            break
    if not placed:
        slots[-1] += 1


def _emit_cumulative_buckets(
    samples: List[MetricSample],
    *,
    name: str,
    help_text: str,
    bucket_counts: Mapping[Tuple[Tuple[str, str], ...], List[int]],
    edges: Sequence[float],
) -> None:
    for base_labels, slots in sorted(bucket_counts.items()):
        base = dict(base_labels)
        running = 0
        for i, edge in enumerate(edges):
            running += slots[i]
            labels = dict(base)
            labels["le"] = _format_le(edge)
            samples.append(
                MetricSample(
                    name=name,
                    labels=_labels_tuple(labels),
                    value=float(running),
                    help=help_text,
                )
            )
        running += slots[-1]
        labels = dict(base)
        labels["le"] = "+Inf"
        samples.append(
            MetricSample(
                name=name,
                labels=_labels_tuple(labels),
                value=float(running),
                help=help_text,
            )
        )


def _format_le(edge: float) -> str:
    if edge == int(edge):
        return str(int(edge))
    return repr(float(edge))


def _module_duration_ms(row: Mapping[str, object]) -> Optional[float]:
    dur = row.get("duration_ms")
    if dur is None:
        return None
    try:
        value = float(dur)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


def build_retained_run_snapshot(
    inventory: InventoryScanResult,
    *,
    duration_buckets_s: Sequence[float] = DEFAULT_DURATION_BUCKETS_S,
) -> RetainedRunSnapshot:
    """Aggregate retained runs into gauge / histogram-bucket samples."""
    edges = _bucket_edges(duration_buckets_s)
    run_counts: Dict[Tuple[Tuple[str, str], ...], float] = defaultdict(float)
    wall_sum: Dict[Tuple[Tuple[str, str], ...], float] = defaultdict(float)
    wall_count: Dict[Tuple[Tuple[str, str], ...], float] = defaultdict(float)
    wall_buckets: Dict[Tuple[Tuple[str, str], ...], List[int]] = {}
    module_counts: Dict[Tuple[Tuple[str, str], ...], float] = defaultdict(float)
    module_buckets: Dict[Tuple[Tuple[str, str], ...], List[int]] = {}
    llm_counts: Dict[Tuple[Tuple[str, str], ...], float] = defaultdict(float)

    with_sidecar = 0
    without_sidecar = 0

    for ref in inventory.runs:
        sidecar = _load_sidecar_for_ref(ref)
        if sidecar is None:
            without_sidecar += 1
            execution_status = "unknown"
            mode = "unknown"
            cache_provenance = "unknown"
            wall_ms: Optional[float] = None
        else:
            with_sidecar += 1
            execution_status = _norm_label_value(
                sidecar.execution_status.value, fallback="unknown"
            )
            mode = _norm_mode(
                sidecar.analysis.mode if sidecar.analysis is not None else None
            )
            cache_provenance = _norm_label_value(
                sidecar.cache_provenance.value, fallback="unknown"
            )
            wall_ms = sidecar.wall_clock_duration_ms
            _accumulate_llm(llm_counts, sidecar)

        run_labels = {
            "target_type": ref.target_type,
            "execution_status": execution_status,
            "mode": mode,
            "cache_provenance": cache_provenance,
        }
        _inc(run_counts, run_labels)

        target_labels = {"target_type": ref.target_type}
        if wall_ms is not None:
            wall_s = wall_ms / 1000.0
            _inc(wall_sum, target_labels, wall_s)
            _inc(wall_count, target_labels, 1.0)
            _observe_bucket(
                wall_buckets,
                base_labels=target_labels,
                value_s=wall_s,
                edges=edges,
            )

        outcomes = ref.run_results.get("module_outcomes")
        if isinstance(outcomes, list):
            for row in outcomes:
                if not isinstance(row, dict):
                    continue
                module_id = _norm_label_value(
                    str(row.get("module_id") or ""), fallback="unknown"
                )
                status = _norm_module_status(
                    str(row.get("execution_status") or row.get("status") or "")
                )
                _inc(
                    module_counts,
                    {"module_id": module_id, "status": status},
                )
                duration_ms = _module_duration_ms(row)
                if duration_ms is not None and status in {
                    "run",
                    "succeeded",
                    "failed",
                }:
                    _observe_bucket(
                        module_buckets,
                        base_labels={"module_id": module_id},
                        value_s=duration_ms / 1000.0,
                        edges=edges,
                    )

    samples: List[MetricSample] = []

    def _emit_dict(
        name: str,
        help_text: str,
        data: Mapping[Tuple[Tuple[str, str], ...], float],
    ) -> None:
        for labels, value in sorted(data.items()):
            samples.append(
                MetricSample(
                    name=name,
                    labels=labels,
                    value=float(value),
                    help=help_text,
                )
            )

    _emit_dict(
        "transcriptx_retained_runs",
        "Currently retained committed analysis runs (regenerated each scan).",
        run_counts,
    )
    _emit_cumulative_buckets(
        samples,
        name="transcriptx_retained_run_wall_seconds_bucket",
        help_text=(
            "Retained-run wall-clock duration histogram buckets in seconds "
            "(gauge snapshot; cumulative counts)."
        ),
        bucket_counts=wall_buckets,
        edges=edges,
    )
    _emit_dict(
        "transcriptx_retained_run_wall_seconds_sum",
        "Sum of retained-run wall-clock durations in seconds (gauge snapshot).",
        wall_sum,
    )
    _emit_dict(
        "transcriptx_retained_run_wall_seconds_count",
        "Count of retained runs with a wall-clock duration (gauge snapshot).",
        wall_count,
    )
    _emit_dict(
        "transcriptx_retained_module_outcomes",
        "Module outcomes across retained committed runs (gauge snapshot).",
        module_counts,
    )
    _emit_cumulative_buckets(
        samples,
        name="transcriptx_retained_module_duration_seconds_bucket",
        help_text=(
            "Module duration histogram buckets in seconds for started modules "
            "(gauge snapshot; cumulative counts)."
        ),
        bucket_counts=module_buckets,
        edges=edges,
    )
    _emit_dict(
        "transcriptx_retained_llm_calls",
        "LLM logical-call counts from retained run_performance sidecars "
        "(gauge snapshot; capped model identity).",
        llm_counts,
    )

    samples.append(
        MetricSample(
            name="transcriptx_retained_scan_candidates",
            labels=(),
            value=float(inventory.candidates_seen),
            help="Run directories examined in the latest retained-run scan.",
        )
    )
    samples.append(
        MetricSample(
            name="transcriptx_retained_scan_errors",
            labels=(),
            value=float(inventory.errors),
            help="Per-candidate scan faults isolated in the latest scan.",
        )
    )
    samples.append(
        MetricSample(
            name="transcriptx_retained_runs_with_sidecar",
            labels=(),
            value=float(with_sidecar),
            help="Retained committed runs with a loadable run_performance sidecar.",
        )
    )
    samples.append(
        MetricSample(
            name="transcriptx_retained_runs_without_sidecar",
            labels=(),
            value=float(without_sidecar),
            help="Retained committed runs missing or unusable performance sidecar.",
        )
    )
    samples.append(
        MetricSample(
            name="transcriptx_retained_scan_truncated",
            labels=(),
            value=1.0 if inventory.truncated else 0.0,
            help="1 if the latest scan hit max_runs; else 0.",
        )
    )

    return RetainedRunSnapshot(
        samples=samples,
        inventory=inventory,
        runs_with_sidecar=with_sidecar,
        runs_without_sidecar=without_sidecar,
    )


def _load_sidecar_for_ref(ref: CommittedRunRef) -> Optional[RunPerformanceV1]:
    loaded = load_run_performance(
        ref.run_root,
        expected_run_id=ref.run_id,
        expected_target_type=ref.target_type,
    )
    if loaded.status != RunPerformanceLoadStatus.ok or loaded.payload is None:
        return None
    return loaded.payload


def _accumulate_llm(
    llm_counts: Dict[Tuple[Tuple[str, str], ...], float],
    sidecar: RunPerformanceV1,
) -> None:
    if sidecar.llm is None:
        return
    models = sidecar.llm.models or []
    model = _norm_model(models[0] if models else None)
    success = int(sidecar.llm.success_count or 0)
    failure = int(sidecar.llm.failure_count or 0)
    if success:
        _inc(llm_counts, {"model": model, "result": "success"}, float(success))
    if failure:
        _inc(llm_counts, {"model": model, "result": "failure"}, float(failure))


def render_prometheus_textfile(snapshot: RetainedRunSnapshot) -> str:
    """Render a Prometheus textfile exposition of gauge snapshot samples."""
    by_name: Dict[str, List[MetricSample]] = {}
    for sample in snapshot.samples:
        by_name.setdefault(sample.name, []).append(sample)

    lines: List[str] = [
        "# TranscriptX retained-run performance snapshot.",
        "# Regenerated each export; gauges shrink when run dirs are deleted.",
        "# Exposition uses gauge types only (no ingest counters / mtime state).",
    ]
    for name in sorted(by_name):
        group = by_name[name]
        help_text = group[0].help.replace("\\", "\\\\").replace("\n", " ")
        metric_type = group[0].type
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {metric_type}")
        for sample in sorted(group, key=lambda s: s.labels):
            if sample.labels:
                label_str = ",".join(
                    f'{k}="{_escape_label(v)}"' for k, v in sample.labels
                )
                lines.append(f"{name}{{{label_str}}} {_format_value(sample.value)}")
            else:
                lines.append(f"{name} {_format_value(sample.value)}")
    lines.append("")
    return "\n".join(lines)


def _format_value(value: float) -> str:
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return repr(float(value))


def assert_no_banned_labels(samples: Iterable[MetricSample]) -> None:
    for sample in samples:
        for key, _ in sample.labels:
            if key in BANNED_LABEL_KEYS:
                raise AssertionError(f"banned label present: {key}")
            if key.endswith("_id") and key not in {"module_id"}:
                raise AssertionError(f"banned label pattern present: {key}")


def export_retained_run_snapshot(
    config: Optional[SnapshotExportConfig] = None,
) -> SnapshotExportResult:
    """Scan retained committed runs and atomically write a Prometheus textfile."""
    cfg = config if config is not None else config_from_env()
    inventory = scan_committed_runs(
        outputs_dir=cfg.outputs_dir,
        group_outputs_dir=cfg.group_outputs_dir,
        max_runs=cfg.max_runs,
    )
    snapshot = build_retained_run_snapshot(
        inventory, duration_buckets_s=cfg.duration_buckets_s
    )
    assert_no_banned_labels(snapshot.samples)
    body = render_prometheus_textfile(snapshot)
    written = write_text(cfg.textfile_path, body)
    logger.info(
        "Wrote retained-run performance snapshot (%s runs, %s candidates) to %s",
        len(inventory.runs),
        inventory.candidates_seen,
        written,
    )
    return SnapshotExportResult(
        textfile_path=written,
        runs_exported=len(inventory.runs),
        candidates_seen=inventory.candidates_seen,
        scan_errors=inventory.errors,
        truncated=inventory.truncated,
        runs_with_sidecar=snapshot.runs_with_sidecar,
        runs_without_sidecar=snapshot.runs_without_sidecar,
    )
