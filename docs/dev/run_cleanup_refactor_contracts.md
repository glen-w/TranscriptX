# Run cleanup refactor — frozen contracts (Phase 0)

**Date:** 2026-07-17  
**Authority:** Cursor plan `cleanup_refactor_full` (Phase 0–B).  
**Status:** Phase A extraction **complete**. Phase B hardening **complete** (policy 7 / journal schema 3 / result schema 2).  
**Scope of this doc:** Contracts frozen for Phase A extraction; version table below reflects live Phase B constants.

## Version freeze (live)

| Constant | Value | Module | Notes |
|----------|------:|--------|-------|
| `CLEANUP_POLICY_VERSION` | 7 | `run_cleanup.models` | Phase B R2: classifier + newest-run versions bound into plan ID |
| `JOURNAL_SCHEMA_VERSION` | 3 | `run_cleanup.models` | Current write schema; readers are version-dispatched |
| `CLEANUP_RESULT_SCHEMA_VERSION` | 2 | `run_cleanup.models` | Phase B1: omit legacy result `root_kind` |

Phase A froze 4/3. Phase B bumps keep schema-3 recovery green via version-dispatched readers.

## Public façade freeze

### Constructor (`RunCleanupService.__init__`)

Keyword-only parameters (all optional with path defaults from `path_constants`):

- `outputs_dir`, `group_outputs_dir`, `state_dir`, `project_root`, `data_dir`, `config_dir`
- `protected_paths`, `protected_path_getter`, `cache_invalidator`

Observable attributes after construction: `outputs_dir`, `group_outputs_dir`, `state_dir`, `project_root`, `data_dir`, `config_dir`.

Phase A constructs `CleanupRuntime` via a **private factory**; the public constructor signature must not change.

### Public methods

| Method | Signature shape | Return |
|--------|-----------------|--------|
| `preview_cleanup` | `(self, mode: CleanupMode, session_id: str)` | `tuple[str, CleanupPreview]` |
| `execute_cleanup` | `(self, handle_token: str, authorization: CleanupAuthorization, session_id: str)` | `CleanupResult` |
| `list_pending_staging` | `(self)` | `list[dict]` |
| `retry_interrupted_staging` | `(self, operation_id: str)` | `CleanupResult` |

Characterisation snapshots `inspect.signature` (names, keyword-only, defaults) and must remain identical through Phase A.

### Package exports

[`run_cleanup/__init__.py`](../../src/transcriptx/web/services/run_cleanup/__init__.py) `__all__` is frozen for Phase A (service, models, confirmation phrases, coded errors, status enums).

### UI / phrases / coded errors

- Confirmation phrases: `CONFIRM_DELETE_ALL`, `CONFIRM_DELETE_OLD` (exact match, no trim)
- Coded errors include `CLEANUP_BUSY`, `PLATFORM_UNSUPPORTED`, `HANDLE_STORE_FULL`
- Streamlit session keys and handle-consumption semantics unchanged
- [`storage_panel.py`](../../src/transcriptx/web/ui/settings/storage_panel.py) must call only the public façade during Phase A

## Ordering contract (current implementation — Phase A must preserve)

1. Gate acquisition  
2. Handle claim  
3. Authorization  
4. Platform check  
5. Root validation / unlocked rediscovery  
6. Lock acquisition  
7. Locked rediscovery  
8. Durable journal creation (initial intent)  
9. Exclusive operation-staging-directory provisioning  
10. Rename(s)  
11. Staged identity proof  
12. Durable staged state  
13. Physical verification  
14. Durable delete intent  
15. Physical deletion  
16. Per-target `physical_deleted` journal update  
17. Parent pruning  
18. **Cache invalidation**  
19. **Terminal operation-journal update**  
20. Handle-result storage  

Cache invalidation **before** terminal journal is required in Phase A. Reordering is Phase B + policy decision.

## Fault-point registry freeze

Exact tuple in [`faults.FAULT_POINTS`](../../src/transcriptx/web/services/run_cleanup/faults.py). Phase A must not add, remove, rename, duplicate, or change mutation-relative positions. Characterisation snapshots the registry and relative order around mutations.

## Acceptance gate command (Phase A + B)

```bash
pytest tests/unit/test_run_cleanup_results.py \
       tests/web/services/test_run_cleanup_journal_ops.py \
       tests/web/services/test_run_cleanup_runtime.py \
       tests/web/services/test_run_cleanup_finalization.py \
       tests/web/services/test_run_cleanup_version_dispatch.py \
       tests/web/services/test_run_cleanup_capacity.py \
       tests/web/services/test_run_cleanup_journal_rmw_lock.py \
       tests/web/services/run_cleanup_characterisation/ \
       tests/web/services/test_run_cleanup_acceptance.py \
       tests/web/services/test_run_cleanup_recoverability.py \
       tests/web/services/test_run_cleanup_release_blockers.py \
       tests/web/services/test_run_cleanup_bulk_depth.py \
       tests/web/services/test_run_cleanup_journal.py \
       tests/web/services/test_run_cleanup_compare_session.py \
       tests/web/services/test_run_cleanup_path_helpers.py \
       tests/web/services/run_cleanup_adversarial/ \
       tests/web/test_storage_cleanup_ui_contracts.py \
       tests/web/services/test_run_cleanup_import_graph.py -q
```

## Phase A side-effect parity

Beyond returned outcomes, preserve: journal write count, cache invalidation count, lock acquire/release order, handle-store calls, logger severity for coded failures, and no extra filesystem probes after authorization.

## Golden-snapshot normalisation

- Freeze operation IDs and clocks via test monkeypatches  
- Replace temporary absolute roots with stable tokens  
- Normalise path separators and errno text  
- Compare raw journal bytes only after nondeterministic fields are controlled  

## Version-decision rubric (Phase B)

| Change class | Decision |
|--------------|----------|
| Persisted journal structure or interpretation | **Schema** |
| Candidate selection, plan identity, auth, staleness, status, visible results | **Policy** |
| Internal refactor with identical serialized + public behaviour | **No bump** |

## Temporary façade shims

**Removed (Phase B-pre).** Callers use `path_helpers.validate_roots`, `deletion_phase.physical_delete_one`, and `results.status_from_journal_targets` directly.
