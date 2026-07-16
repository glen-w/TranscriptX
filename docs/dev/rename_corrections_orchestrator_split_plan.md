<!-- Planning doc: review only. No implementation committed with this file. -->

# Rename + corrections orchestrator split — stepwise plan

**Source:** 2026-07-16 refactor assessment (Top 3). Behavior-preserving incremental plans.

Index: [`docs/dev/refactor_top3_index_2026-07-16.md`](refactor_top3_index_2026-07-16.md)

## Candidate 3 — Split rename + corrections orchestrators

### 1. Goal

Finish structural extraction of already-phased rename and corrections-generation orchestrators into focused modules so `pipeline.py` (~933 L) and `candidate_service.py` (~852 L) become thin coordinators—**behavior-preserving**, after characterization.

### 2. Current state

**Rename (partially phased):**

| Module | Responsibility |
|--------|----------------|
| `rename/plan.py` | `build_rename_plan`, `RenamePlan`, rollback policy |
| `rename/journal.py` | journal I/O, lock path, `discover_incomplete_renames` |
| `rename/finalize.py` | output-dir move + artifact remap |
| `rename/names.py`, `outcome.py`, `io_atomic.py`, `sidecars.py`, `processing_state.py`, `audio_association.py` | supporting |
| **`rename/pipeline.py` (~933 L)** | Still owns: lock → journal → txn → finalize → reconcile → repair orchestration |
| `file_rename.py` | Compatibility shim + monkeypatch surface over `rename.*` |

**Key pipeline symbols to keep stable as public API:**  
`rename_managed_transcript`, `repair_managed_rename`, `rename_transcript_files`, `rename_transcript_files_with_outcome`, plus phase helpers `_run_under_lock`, `_execute_rename_transaction`, `_run_finalize_phase`, `_run_reconcile_phase`, `_post_commit_pipeline`, `_close_journal_and_build_outcome`.

**Corrections Studio:**

| Piece | Notes |
|-------|-------|
| `candidate_service.py` | `CorrectionsStudioCandidateService`; `generate_candidates` ~225 L |
| Already private steps | `_load_generation_inputs`, `_run_detectors`, `_pre_dedupe_aggregate`, `_build_diagnostics`, `_build_manifest_and_log`, `_studio_candidates_from_annotated`, `_commit_generation_batch` |
| Adjacent | `generation_manifest.py`, `llm/discovery.py`, `llm/merge.py`, session store optimistic commit |

### 3. Preconditions / characterization tests

**Rename (run/extend before moves):**

- `tests/integration/test_rename_e2e.py`
- `tests/core/utils/test_rename_managed_contracts.py`
- `tests/core/utils/test_file_rename_contracts.py`
- `tests/core/utils/test_rename_robustness.py`
- `tests/core/utils/test_rename_finalize_and_layout.py`
- `tests/core/utils/test_rename_transaction_unit.py`

Add/ensure a **phase matrix** table test: for each `JournalPhase` / failure injection point (lock fail, journal persist fail, txn fail, finalize fail, reconcile fail, repair from prepared/committed), assert `RenameStatus` + error codes unchanged.

**Corrections:**

- `tests/services/test_corrections_studio_candidate_invariants.py`
- `tests/services/test_corrections_studio*.py` (manifest, fuzzy, persistence, hardening)
- `tests/integration/core/test_corrections_studio_roundtrip_integration.py`

Add golden for `generate_candidates` with LLM disabled: candidate count by kind, manifest hash stability, commit-abort path (`GenerationCommitConflict` → `commit_aborted=True`).

### 4. Step-by-step plan

#### A. Rename

| Step | Work | Effort | Behavior change? |
|------|------|--------|------------------|
| **3.1** | Characterization PR only: phase matrix + document status truth table (no production moves) | S–M | No |
| **3.2** | Extract `_execute_rename_transaction` + `_mark_transaction_committed` → `rename/transaction_phase.py` (or extend existing txn module); re-export from pipeline | S | No |
| **3.3** | Extract `_run_finalize_phase` coordination that remains in pipeline into `finalize.py` or `finalize_phase.py` (low-level move already in `finalize.py`) | S | No |
| **3.4** | Extract `_run_reconcile_phase` + slug updates → `rename/reconcile.py` | S–M | No |
| **3.5** | Extract `repair_managed_rename` → `rename/repair.py`; pipeline imports it | M | No |
| **3.6** | Leave `rename_managed_transcript` / `_run_under_lock` / `_post_commit_pipeline` as ~150–250 L orchestrator | S | No |
| **3.7** | Slim `file_rename.py`: only re-exports + documented monkeypatch attrs; no logic growth | S | No (imports stable) |

#### B. Corrections candidates

| Step | Work | Effort | Behavior change? |
|------|------|--------|------------------|
| **3.8** | Characterization: LLM-off generation golden + commit-abort test | S | No |
| **3.9** | Move pure helpers (`_enrich_occurrences`, `_detector_counts_*`, `_db_rule_to_engine_rule`, `_GenerationInputs`) → `candidate_generation_inputs.py` / `candidate_mapping.py` | S | No |
| **3.10** | Move `_run_detectors` + `_pre_dedupe_aggregate` → `candidate_detection.py` | S | No |
| **3.11** | Move `_studio_candidates_from_annotated` + provenance wiring → `candidate_materialize.py` | S | No |
| **3.12** | Move `_commit_generation_batch` → `candidate_commit.py` (keep optimistic preconditions identical) | M | No |
| **3.13** | `generate_candidates` becomes linear orchestration calling the above; stay on `CorrectionsStudioCandidateService` as facade | S | No |

**Do not** in these PRs: change detector versions, manifest fields, review migration, or LLM discovery contracts.

### 5. Done criteria

- `pipeline.py` primarily orchestrates phases; repair/reconcile/txn live in named modules.
- `candidate_service.generate_candidates` reads as a short pipeline; helpers unit-testable without full Studio UI.
- Public imports (`transcriptx.core.utils.rename`, `file_rename`, `CorrectionsStudioCandidateService.generate_candidates`) unchanged.
- Phase matrix + corrections goldens green; E2E rename + studio roundtrip green.

### 6. Risk notes & rollback

- **Risk: Medium–High** — rename is a durability state machine; corrections commit is concurrency-sensitive.
- Monkeypatches in tests often target `file_rename` or pipeline private names — preserve aliases or update tests in the **same** PR as moves.
- Journal phase transitions must remain byte-identical in outcomes.
- **Rollback:** revert single extraction PR; characterization tests stay to catch accidental behavior drift later.

### 7. Estimated effort

| Scope | Effort |
|-------|--------|
| 3.1 + 3.8 characterization | **S–M** |
| Rename splits 3.2–3.7 | **M** (~3–5 d) |
| Corrections splits 3.9–3.13 | **M** (~3–5 d) |
| **Overall Candidate 3** | **L** if done carefully with char tests first; **M** of pure move work |

---
