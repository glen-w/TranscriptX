# RunCleanupService refactor plan — assessment & edits

**Plan assessed:** Cursor plan `cleanup_service_refactor` (extract orchestration from [`service.py`](../../src/transcriptx/web/services/run_cleanup/service.py)).  
**Date:** 2026-07-17  
**Status:** Recommendations reviewed and **folded into the plan** (all five adopted; Runtime kept as its own PR rather than folded into locks). Phase 0 characterisation suite and Phase A `staging_identity` / `CleanupRuntime` scaffolding are in progress in-tree.  
**Verdict:** Direction is sound (façade + move-only PRs + strong safety-net suite). Five edits below make implementation smoother and reduce the highest real failure modes: monkeypatch drift, circular `self` coupling, and silent result-shape regressions.

---

## What already works

- Correct non-goals (no policy/journal/auth changes).
- Right end-state: primitives stay in `staging` / `physical_delete` / `journal`; orchestration leaves `service.py`.
- Extract order is mostly risk-ordered (factories → helpers → stage/delete → retry → execute).
- Explicit awareness of private test call sites and `fault_point` name stability.
- Full safety-net command is the right merge bar for later PRs.

---

## Gaps that will hurt mid-flight

1. **`self`-graph is denser than the plan admits.** `_stage_one`, `_physical_delete_one`, retry, and `_execute_claimed` all call `_persist_target_state`, `_output_root_for_target`, `_planned_root_for_target`, `_prune_subject_parent`, `_invalidate_caches`, `_new_journaled_operation`. Extracting stage/delete without a shared runtime bag forces either “pass `svc` everywhere” (circular imports) or huge parameter lists that churn every PR.

2. **Monkeypatch guidance contradicts itself.** PR4 says both keep `service.journal` / `service.rename_into_staging` aliases *and* update recoverability patches to new modules. After move, only the **import site that executes** is patchable. Aliases on `service` do nothing if `stage_target` imports `journal` directly.

3. **Wrapper limbo in PR3/PR4.** Leaving `self._acquire_locks` / `self._stage_one` as thin wrappers “for later PRs” means PR6 still rewires every call site under maximum blast radius. Prefer switch-callers-in-same-PR.

4. **PR1 can silently change semantics.** Early-exit `CleanupResult` / `CleanupTargetResult` blocks are not identical (warnings source, empty vs retained targets, optional `filesystem_dev`/`ino`, whether `store_result` is called). Factories without a parity checklist will look green on shallow gates and fail release blockers later.

5. **PR2 is too small to pay for a separate merge.** Status helpers are ~60 LOC of pure functions; a dedicated PR mainly adds rebase noise.

---

## Recommended high-leverage edits (apply to the plan)

### 1. Add a `CleanupRuntime` context before any phase extract

**Edit the plan:** After factories (or as the first step of PR3), introduce a small frozen/dataclass bag owned by the façade and passed into extracted functions:

```text
CleanupRuntime
  outputs_dir, group_outputs_dir, state_dir
  persist_target_state(...)   # bound method or free fn + state_dir
  output_root_for_target(...)
  planned_root_for_target(...)
  invalidate_caches(...)
  prune_subject_parent(...)   # optional; can stay on service until execute PR
```

**Why:** Decouples `stage_target` / `delete_target` / `retry` / `execute_pipeline` from importing `RunCleanupService`. Prevents circular imports and stops every extract from inventing a new kwargs soup.

**Implementation note:** Build the runtime in `__init__` or at the start of `execute_cleanup` / `retry_interrupted_staging`; do not put Streamlit or handle-store on it.

---

### 2. Adopt one monkeypatch rule (delete the dual strategy)

**Replace PR4’s dual guidance with:**

> Patch at the **defining module** of the symbol the running code imports. When a call moves, update recoverability monkeypatch paths in the **same PR**. Do not keep dead `service.journal` / `service.rename_into_staging` aliases for patchability.

Concrete mapping after PR4:

| Current patch target | New target after move |
|----------------------|------------------------|
| `...service.rename_into_staging` | `...stage_target.rename_into_staging` (or `...staging.rename_into_staging` if stage_target uses that binding) |
| `...service.journal.update_target_state` | module that calls it (`stage_target` / `delete_target` / `retry` / shared persist helper) |
| `...service.journal.update_operation_status` | owning execute/retry module |
| `...service.journal.claim_retry_ownership` | `retry` module |

**Why:** Removes the most likely “tests green locally / red after extract” footgun. One rule is easier to review than “aliases or update patches.”

---

### 3. Extract journal persistence helpers before stage/delete

**Insert a PR (or fold into end of factories / start of stage PR):**

Move `_persist_target_state` and `_new_journaled_operation` into e.g. `journal_ops.py` (or a section of `journal.py` if you want fewer files). Stage, delete, retry, and execute all depend on these; they are shared infrastructure, not “service leftovers.”

Keep `RunCleanupService._persist_target_state` as a one-line shim **only if** a test still calls it (today none do via private API — `_physical_delete_one` is the private delete shim that matters).

**Why:** PR4/PR5/PR6 otherwise each re-bind persistence differently. One shared helper makes durability/`require_durable` behavior impossible to fork.

---

### 4. Merge PR2 into PR1; ban long-lived thin wrappers

**Edit sequencing:**

| Old | New |
|-----|-----|
| PR1 factories | **PR1** factories **+** status helpers (`status.py`) + façade shims for `_status_from_journal_targets` |
| PR2 status | *(deleted)* |
| PR3 locks/revalidate with wrappers | **PR2** locks + revalidate as **module functions**; **switch `_execute_claimed` call sites in the same PR** |
| PR4–6 | renumber to PR3–5 |

Rule for every extract PR: *no* “wrapper now, rewire later.” Either the body stays on the class, or callers import the new function immediately. Temporary shims are allowed only for **external** private test call sites (`_physical_delete_one`, `_status_from_journal_targets`, `_validate_roots`).

**Why:** Cuts one merge cycle and prevents a half-migrated `self._*` call graph that makes the final execute extract brutal.

---

### 5. Harden PR1 with a result-parity checklist and a wider gate

**Add to PR1 acceptance criteria:**

- Factories must preserve **exact** field sets per call site class:
  - `blocked` / `stale` / `failed_before_mutation`: whether `warnings` come from `plan` vs `()`
  - `noop`: retained-target projection (RETAINED rows) vs empty `targets`
  - `target_result_from`: always copy identity fields (`filesystem_dev`, `filesystem_ino`, `root_kind`) unless the current site intentionally omits them — do not “improve” omissions in this PR
- Prefer **named factories over `**overrides`** for the first pass (overrides hide missing required fields).
- Make `with_updates` **required** for `_finalise_operation` (not optional) *or* leave finalise construction untouched until the execute PR — do not half-adopt it.
- **Gate expansion:** include `test_run_cleanup_recoverability.py` in PR1 (not only acceptance/bulk/release). Recoverability asserts demotions and terminal status that factories can accidentally alter.

**Why:** PR1 looks like pure cosmetics but touches every early-exit and target row shape; that is where silent behavioral drift starts.

---

## Suggested revised PR ladder (after edits)

```text
PR1  result_factories + status helpers + parity checklist
     gate: acceptance + bulk + release_blockers + recoverability + journal status vector

PR2  CleanupRuntime + journal_ops (_persist / _new_journaled)
     gate: acceptance + recoverability (smoke) 

PR3  locks + revalidate (module fns; call sites switched)
     gate: acceptance races + release blockers

PR4  stage_target + delete_target + update recoverability monkeypatches
     shims: _physical_delete_one
     gate: full safety net

PR5  retry module (uses CleanupRuntime + delete_target)
     gate: recoverability + release retry matrix + UI pending-retry

PR6  execute_pipeline (A–M kept intact; gate/finally ownership documented)
     gate: full safety net + UI contracts
```

Still six merges if you keep Runtime separate; acceptable. If you need fewer merges, fold **PR2 Runtime + journal_ops into the start of PR3** — do not fold Runtime into PR1 (factories should stay mechanically boring).

---

## Explicit keep / still do not do

- Keep: move-only discipline, fault_point names, public façade, policy/schema versions frozen.
- Keep: execute phase machine unsplit in the final PR.
- Do not: expand staging.py with the full `_stage_one` journal state machine if that file is already the FS primitive layer — `stage_target.py` is the right split.
- Do not: mix with config / shared analysis I/O / corrections refactors.

---

## Bottom line

The plan is implementable as written, but will be smoother if you (1) introduce a runtime context, (2) pick one monkeypatch rule, (3) extract persistence before stage/delete, (4) kill wrapper limbo / merge the tiny status PR, and (5) treat factory extraction as a semantic surface with a wider gate. Those five edits address the failure modes most likely to burn a day mid-series; everything else in the original plan can stay.
