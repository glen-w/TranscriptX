<!-- Living compatibility table for Candidate 3 orchestrator split. -->

# Rename + corrections orchestrator — compatibility table

| old import path | new owner | temporary alias | tests/callers requiring migration | alias removal condition |
|-----------------|-----------|-----------------|-----------------------------------|-------------------------|
| `rename.pipeline._execute_rename_transaction` | `rename.transaction_phase` | re-export on `pipeline` | none | R7 search clean |
| `rename.pipeline._mark_transaction_committed` | `rename.transaction_phase` | re-export on `pipeline` | none | R7 |
| `rename.pipeline._run_finalize_phase` | `rename.finalize_phase` | re-export on `pipeline` | none | R7 |
| `rename.pipeline._run_reconcile_phase` | `rename.reconcile` | re-export on `pipeline` | none | R7 |
| `rename.pipeline._post_commit_pipeline` | `rename.post_commit` | re-export on `pipeline` | none | R7 |
| `rename.pipeline._close_journal_and_build_outcome` | `rename.post_commit` | re-export on `pipeline` | none | R7 |
| `rename.pipeline.repair_managed_rename` | `rename.repair` | re-export on `pipeline` + `__init__` + `file_rename` | public paths unchanged | keep public forever |
| `rename.pipeline._safe_persist_journal` | `rename.journal` | re-export on `pipeline` | done | done |
| `candidate_service._enrich_occurrences` | `candidate_mapping` | re-export on `candidate_service` | invariants | C4 |
| `candidate_service._detector_counts_*` | `candidate_diagnostics` | re-export | invariants | C4 |
| `candidate_service._db_rule_to_engine_rule` | `candidate_mapping` | re-export | studio tests | C4 |
| `candidate_service._commit_generation_batch` | `candidate_commit.commit_generation_batch` | optional alias | conflict golden | C4 |

## Patch inventory (post rename extract)

| Patch string | Resolve site |
|--------------|--------------|
| `rename.journal.persist_journal` | `_safe_persist_journal` in journal |
| `rename.finalize_phase.finalize_output_directory_move` | finalize_phase |
| `rename.finalize_phase.execute_artifact_remap` | finalize_phase |
| `rename.reconcile.invalidate_path_cache` | reconcile |
| `rename.pipeline.FileLock` | rename_managed_transcript lock |
| `rename.repair.FileLock` | repair_managed_rename lock |
| `rename.pipeline.PROCESSING_STATE_FILE` | pipeline state redirect |
