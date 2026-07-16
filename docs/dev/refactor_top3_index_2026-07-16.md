<!-- Planning doc: review only. No implementation committed with this file. -->

# TranscriptX — Top 3 refactor plans (index)

**Source:** 2026-07-16 refactor assessment (Top 3). Behavior-preserving incremental plans.

Related docs:

- Config migration: [`docs/config/pydantic_migration.md`](../config/pydantic_migration.md), [`docs/config/config_knobs_refactor_plan.md`](../config/config_knobs_refactor_plan.md)
- Candidate 1 detail: [`docs/config/config_ownership_collapse_plan.md`](../config/config_ownership_collapse_plan.md)
- Candidate 2 detail: [`docs/dev/shared_analysis_io_refactor_plan.md`](shared_analysis_io_refactor_plan.md)
- Candidate 3 detail: [`docs/dev/rename_corrections_orchestrator_split_plan.md`](rename_corrections_orchestrator_split_plan.md)

## Recommended sequencing

| Order | Candidate | Why |
|-------|-----------|-----|
| **1st (start now)** | **#2 Shared analysis I/O** | Lowest risk; no settings surface; high LOC payoff; can ship while config work continues |
| **1st parallel track** | **#1 Config ownership collapse** | Already mid-flight (registry complete; 8 subtrees delegated); keep momentum on Batch 5+ |
| **2nd / after char tests** | **#3 Rename + corrections split** | Medium–high; needs E2E characterization first; do not interleave with config validation PRs |

**Parallelism:** Candidate 2 is independent of 1 and 3. Candidate 1 and 3 both touch “careful state machines / settings”; avoid same-week mega-PRs that change both. Within #1, do one nested subtree per PR.

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

Ship **#2** for quick, safe wins; continue **#1** one subtree per PR using the existing hydrate recipe; only then tackle **#3**, starting with characterization tests so splits stay boring.
