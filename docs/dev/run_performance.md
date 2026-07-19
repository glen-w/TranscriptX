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

### group

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
