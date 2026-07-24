<!-- Planning doc: review only. No implementation committed with this file. -->

# TranscriptX — Top 3 refactor plans (index)

**Source:** 2026-07-16 refactor assessment (Top 3). Behavior-preserving incremental plans.

**Status (2026-07-22):** All three Candidates are **Done**. Residual eng (optional config **1.9**, export Jinja2/Artifact Protocol) is outside this Top-3 program.

Related docs:

- Config migration: [`docs/config/pydantic_migration.md`](../config/pydantic_migration.md), [`docs/config/config_knobs_refactor_plan.md`](../config/config_knobs_refactor_plan.md)
- Candidate 1 detail: [`docs/config/config_ownership_collapse_plan.md`](../config/config_ownership_collapse_plan.md)
- Candidate 2 detail: [`docs/dev/shared_analysis_io_refactor_plan.md`](shared_analysis_io_refactor_plan.md)
- Candidate 3 detail: [`docs/dev/rename_corrections_orchestrator_split_plan.md`](rename_corrections_orchestrator_split_plan.md)
- Compat aliases: [`docs/dev/rename_corrections_compat_table.md`](rename_corrections_compat_table.md)

## Recommended sequencing

| Order | Candidate | Why |
|-------|-----------|-----|
| **Done** | **#2 Shared analysis I/O** | Complete 2026-07-17 (affect/dynamics/group-chart + A3 + char) |
| **Done** | **#1 Config ownership collapse** | Complete through 1.8 (2026-07-20+): nested + flat + mapping + system/workflow + atomic file overrides + curated `to_dict`. Live inventory invariant **51 / 705 / 16** (721; +`keyphrases` pilot 2026-07-24). Optional follow-up **1.9** structural split of `analysis.py` is outside Candidate 1 done criteria. |
| **Done** | **#3 Rename + corrections split** | Structural extract complete: `rename/{transaction_phase,finalize_phase,reconcile,repair,post_commit}`; corrections `candidate_*` modules; thin `pipeline.py` / `candidate_service.py` coordinators; public imports unchanged |

**Parallelism:** Candidates 1–3 are complete. Do not reopen them for optional config 1.9 or unrelated product work.

---

## Explicit non-goals (all three)

Do **not** do these while executing these plans:

- Full rewrite of `TranscriptXConfig` / Hydra / Dynaconf / OmegaConf / `BaseSettings`
- Replacing the dataclass attribute API modules use (`get_config().analysis.*`)
- Adding vanity registry pilots or new validators (Cerberus/Marshmallow/jsonschema)
- Rewriting analysis *algorithms* (scoring, detection, LLM prompts) under the guise of I/O extraction
- Collapsing group chart *domain* logic into one mega-generator
- Deleting `file_rename.py` shim until all external/test monkeypatches migrate
- Changing rename journal schema / phase enum / rollback policy as part of a “split” PR
- Changing optimistic-commit semantics or generation manifest identity in corrections
- Resolver “no temp-file” rewrite until most nested analysis configs are delegated
- Growing `analysis.py` with new literal defaults (freeze policy)

---

## Cross-plan checklist (every PR)

1. Behavior-preserving by default; call out any intentional change in the PR description.
2. Prefer extract-and-delegate over rewrite.
3. Keep public import paths; use shims when needed.
4. Run the smallest relevant gate + one broader smoke (config gate / rename e2e / analysis module tests).
5. Do not mix Candidate 1 settings changes with Candidate 3 durability moves in one PR.

---

### One-line summary for prioritization

**#1 Config ownership, #2 Shared analysis I/O, and #3 rename/corrections are Done.** Optional config **1.9** is unrelated follow-up. Product capacity → [`analysis_module_backlog_2026-07-17.md`](analysis_module_backlog_2026-07-17.md) (**B9** next).
