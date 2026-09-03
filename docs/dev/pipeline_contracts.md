# Pipeline Contracts (Authoritative)

This document defines behavioral invariants for the core pipeline layering.  
Guides and quickstarts are non-authoritative and should defer to these contracts.

## Run Status Model

- `execution_status`: terminal status from execution before persistence.
- `final_status`: terminal status after persistence outcomes are evaluated.
- `status`: compatibility/read convenience alias and must equal `final_status`.
- This run-level `execution_status` is distinct from `modules_skipped[].execution_status`
  in `run_results.json`, where the field describes module skip classification
  (`skipped` or `blocked`).
- Precedence: `aborted` > `failed` > `partial` > `succeeded`.
- Optional persistence failures may only downgrade `succeeded -> partial`.
- Required persistence failures produce `final_status=failed`.
- Cancellation with required persistence failure:
  - `execution_status=aborted`, `final_status=failed`, `status=failed`,
  - `termination_reason=cancellation`.

## Planner and Executor Boundaries

- Planner API: `DAGPlanner.plan(requested_modules, registry_snapshot) -> ExecutionPlan`.
- Planner consumes immutable `RegistrySnapshot`.
- Planner fails closed for unresolved dependencies.
- Executor owns run-local state and outcome reduction.
- Executor does not persist, log, or report directly.
- Path routing rules:
  - planner cannot consume raw filesystem paths,
  - executor does not construct/normalize/route filesystem paths.

## Persistence Rules

- Required writes: canonical run outputs (`run_results.json` and related artifacts),
  artifact manifest, and run report.
- Conditional required writes: processing state when a matching managed state entry exists.
  If no processing state file or matching entry exists, processing-state persistence is an
  optional no-op.
- Event emission is best-effort runtime notification, not a durable persistence write.
- Optional writes: execution plan artifact, auxiliary artifact index, non-critical snapshots.
- Persistence transaction strategy: fail-fast per write, no rollback of already durable writes.
- Outcomes must be surfaced via `RunResult.persistence_outcomes`.

## Event Contract

- Event sequence:
  - `run_started`,
  - per-module terminal event (`module_completed|module_skipped|module_failed`),
  - single terminal run event (`run_completed|run_failed`) emitted at most once.
- Setup/context failures must emit `run_failed`.
- Callback failures are isolated and must not corrupt run outcome.

## Cleanup Guarantees

Cleanup must execute via `try/finally` for:

- transcript output-dir override lifecycle,
- runtime config override lifecycle,
- draft override lifecycle,
- `PipelineContext.close()`.

## Legacy analysis modules

- Registry entries may set `legacy: bool` on `ModuleInfo`. Legacy modules are **excluded**
  from `ModuleRegistry.get_default_modules(..., include_legacy=False)` (the default when
  `analysis.include_legacy_modules` is `False`).
- Users may still run legacy modules by **explicitly** naming them in the module list, or
  by setting `analysis.include_legacy_modules=True` to pull them back into default-style
  plans without listing IDs.
- Default semantic analysis uses `semantic_similarity`. Legacy IDs
  `semantic_similarity` / `semantic_similarity_advanced` remain stable for outputs and
  backward compatibility.

## Semantic similarity v2

- Module id: `semantic_similarity`. Outputs use `*_semantic_similarity_*.json` with
  top-level `schema_version: semantic_similarity.1.1` (major still `1` under
  `parse_schema_major`). Motif envelope fields: `motifs`, `motif_export_status`,
  `provenance`, `eligible_segment_count`, `comparability` (TF-IDF incomparable).
- Presets: `analysis.active_semantic_similarity_profile` selects
  `analysis.semantic_similarity_profiles` (`fast_v2`, `balanced_v2`, `deep_v2`).
  Runtime merge: dataclass defaults → preset dict → per-field user overrides (values that
  differ from defaults on `analysis.semantic_similarity`) → when the preset omits
  `mode`, `analysis.analysis_mode` (`quick`/`full`) sets `mode` to `basic`/`advanced`.

