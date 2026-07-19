"""Analysis-run performance telemetry (not Streamlit UI perf)."""

from __future__ import annotations

from transcriptx.core.observability.run_performance.exporter import (
    SnapshotExportConfig,
    SnapshotExportResult,
    config_from_env,
    export_retained_run_snapshot,
)
from transcriptx.core.observability.run_performance.inventory import (
    CommittedRunRef,
    InventoryScanResult,
    scan_committed_runs,
)
from transcriptx.core.observability.run_performance.io import (
    RunPerformanceLoadStatus,
    load_run_performance,
    write_run_performance,
)
from transcriptx.core.observability.run_performance.recorder import (
    RunPerformanceRecorder,
)
from transcriptx.core.observability.run_performance.schema import (
    RUN_PERFORMANCE_SCHEMA_VERSION,
    TIMING_SCOPE_VERSION,
)

__all__ = [
    "RunPerformanceRecorder",
    "RUN_PERFORMANCE_SCHEMA_VERSION",
    "TIMING_SCOPE_VERSION",
    "RunPerformanceLoadStatus",
    "load_run_performance",
    "write_run_performance",
    "CommittedRunRef",
    "InventoryScanResult",
    "scan_committed_runs",
    "SnapshotExportConfig",
    "SnapshotExportResult",
    "config_from_env",
    "export_retained_run_snapshot",
]
