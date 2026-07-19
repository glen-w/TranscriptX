Type: PRODUCT
Authority: self

# Analysis-run performance telemetry

Streamlit UI load profiling (`core/observability/perf.py`, `TRANSCRIPTX_STREAMLIT_PERF`) is **unrelated**. This document covers analysis-run wall time, module `duration_ms`, and `.transcriptx/run_performance.json`.

## Phase 0 findings

- Optional `module_outcomes[].duration_ms` / `used_cache` **survive** `load_run_results` without a schema bump (`RUN_RESULTS_SCHEMA_VERSION` remains 2).
- Prefer a narrow validator before a full typed `List[Dict]` → model migration if churn appears.

## Wall-clock scope (`timing_scope_version: 1`)

1. Start at `RunOrchestrator.run` entry (`perf_counter`).
2. Include preparation, execution, and **all required persistence**.
3. Stop after required persistence; write optional `run_performance.json` **outside** the measured interval, still under the same per-run lease.

Group runs use a **separate** recorder; members keep their own.

## Authority

- Module status + `duration_ms`: `run_results.json` only.
- Sidecar: non-authoritative run-level telemetry + stable interpretative context (mode/profile/runtime/workload snapshots allowed).
- `run_report.json`: labelled legacy display fallback only.

## Loader statuses

`missing` | `malformed` | `unsupported_schema` | `oversized` | `io_error` — the loader cannot know “legacy”; the UI uses surrounding run metadata to distinguish old runs from telemetry loss.
