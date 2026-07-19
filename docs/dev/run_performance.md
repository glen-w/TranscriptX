Type: PRODUCT
Authority: self

# Analysis-run performance telemetry

Streamlit UI load profiling (`core/observability/perf.py`, `TRANSCRIPTX_STREAMLIT_PERF`) is **unrelated**. This document covers analysis-run wall time, module `duration_ms`, and `.transcriptx/run_performance.json`.

## Phase 0 findings

- Optional `module_outcomes[].duration_ms` / `used_cache` **survive** `load_run_results` without a schema bump (`RUN_RESULTS_SCHEMA_VERSION` remains 2).
- Prefer a narrow validator before a full typed `List[Dict]` → model migration if churn appears.

## Wall-clock scope (`timing_scope_version: 1`)

### Transcript

1. Start at `RunOrchestrator.run` entry (`perf_counter`).
2. Include preparation, execution, and **all required persistence**.
3. Stop after required persistence; write optional `run_performance.json` **outside** the measured interval, still under the same per-run lease.

### Group

1. Start at entry to the **group branch** of `run_analysis_pipeline` (`perf_counter`).
2. Include sequential member execution and required group finalisation persistence (aggregation/synthesis, required group artifacts, final group `run_results.json` commit and validation).
3. Stop immediately before the optional performance-sidecar write; write `.transcriptx/run_performance.json` **while the group writer lease remains held**.

Group runs use a **separate** recorder; members keep their own. The group recorder is **not** bound as the active ContextVar during member execution (each member `RunOrchestrator` binds and restores its own recorder).

Group wall time is an **independent** end-to-end measurement. Do **not** calculate it by summing member wall times. Group wall may **exceed** the sum of member walls because it includes preparation, aggregation, and persistence overhead.

## Authority

- Module status + `duration_ms`: `run_results.json` only (for members: each member’s file; group rollup does not invent group module timings). Member module timings remain authoritative in member `run_results.json` files.
- Sidecar: non-authoritative run-level telemetry + stable interpretative context (mode/profile/runtime/workload snapshots allowed). Group sidecars include wall time, status, analysis context, workload when available, and `GroupPerformanceMeta` — not member durations or LLM aggregates.
- Group LLM metrics are **not** collected in schema v1 (omit `llm`; do not report zeros). This is an intentional instrumentation gap, not “zero calls”.
- `run_report.json`: labelled legacy display fallback only.
- Optional group sidecar write failure must not invalidate an otherwise committed group run; coded warnings may appear under `group_phase_metadata.performance_sidecar_warning`.

## Loader statuses

`missing` | `malformed` | `unsupported_schema` | `oversized` | `io_error` — the loader cannot know “legacy”; the UI uses surrounding run metadata to distinguish old runs from telemetry loss.

## Phase 2 — Retained-run snapshot exporter

Optional Prometheus **textfile** exporter over **currently retained** committed runs (valid `run_results.json` on disk). Independent of the Streamlit Performance page; GUI never depends on it.

### Design

- Each export cycle **rescans** transcript + group output trees and **regenerates** the entire metric snapshot.
- Metrics are **gauges** (including histogram-bucket cumulative counts). When a run directory is deleted, the next scan simply omits it — gauges shrink.
- **No** mtime-based ingest state file and **no** Prometheus counters that cannot delete observations.
- Committed-run inventory is path-safe, deterministically ordered, capped (`max_runs`), and isolates per-candidate faults. It does **not** use `RunIndex.list_runs` (user-visible artifact filter).

### How to run

```bash
python scripts/export_run_performance_snapshot.py
python scripts/export_run_performance_snapshot.py -o /var/lib/node_exporter/textfile/transcriptx_run_perf.prom
python scripts/export_run_performance_snapshot.py --outputs-dir /path/to/outputs --max-runs 5000
```

Programmatic:

```python
from transcriptx.core.observability.run_performance import (
    SnapshotExportConfig,
    export_retained_run_snapshot,
)

export_retained_run_snapshot(
    SnapshotExportConfig(
        outputs_dir=...,
        group_outputs_dir=...,
        textfile_path=...,
    )
)
```

### Config knobs

| Env / flag | Meaning |
|------------|---------|
| `TRANSCRIPTX_RUN_PERF_EXPORT_PATH` / `--output` | Textfile destination (default: `$TRANSCRIPTX_DATA_DIR/state/run_performance_snapshot.prom`) |
| `TRANSCRIPTX_RUN_PERF_EXPORT_MAX_RUNS` / `--max-runs` | Scan cap (default 10000) |
| `TRANSCRIPTX_OUTPUT_DIR` / `--outputs-dir` | Outputs root |

Compose / node_exporter profile wiring is **deferred** (plan: later).

### Metric universe (low cardinality)

All `# TYPE … gauge`. Labels never include `run_id`, `transcript_key`, paths, fingerprints, or exception text. Model identity is capped/normalised; mode is `quick` \| `full` \| `other` \| `unknown`.

| Metric | Meaning |
|--------|---------|
| `transcriptx_retained_runs{target_type,execution_status,mode,cache_provenance}` | Count of retained committed runs |
| `transcriptx_retained_run_wall_seconds_bucket{target_type,le}` | Cumulative wall-duration histogram buckets (seconds) |
| `transcriptx_retained_run_wall_seconds_sum` / `_count` | Wall duration sum / count |
| `transcriptx_retained_module_outcomes{module_id,status}` | Module outcome counts from `run_results` |
| `transcriptx_retained_module_duration_seconds_bucket{module_id,le}` | Started-module duration buckets |
| `transcriptx_retained_llm_calls{model,result}` | Logical LLM success/failure from sidecars (when present) |
| `transcriptx_retained_scan_*` | Last-scan candidates / errors / truncated / sidecar presence |

Package layout: `inventory.py` (scan), `exporter.py` (aggregate + textfile), `scripts/export_run_performance_snapshot.py`.
