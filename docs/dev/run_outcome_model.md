Type: GUIDE
Authority: ../run_outcome_contract.md

# Run outcome model (developer notes)

**Authority:** All execution-truth rules (statuses, precedence, loaders, group projection) live in **[`docs/run_outcome_contract.md`](../run_outcome_contract.md)**. This guide collects implementation pointers for contributors; it does not define contract rules.

## Where to look in code

| Concern | Module / symbol |
| --- | --- |
| Status projection | `run_outcome_truth.py` |
| Typed loaders | `load_run_results`, `load_run_outcome_context` |
| Schema gate (`schema_version >= 2`) | `assert_run_results_schema_supported` in `module_outcomes` |
| Group rollups | `project_group_outcomes(...)` |
| Group phase metadata | `load_group_phase_metadata(...)` (file: `aggregation_warnings.json` today) |

## Operator-only heuristics

Reporting or discovery code may infer hints from file presence when `run_results.json` is missing. Those heuristics are **not** canonical execution truth — they assist operators only. Canonical status always comes from typed loaders over `run_results.json` (see the contract).

## Decision log anchors

When semantics are ambiguous during implementation, log explicit decisions for:

- blocked vs skipped precedence
- cache-hit interpretation
- partial `run_results` with manifest present
- group/member status rollups

Resolve ambiguities by updating **`docs/run_outcome_contract.md`** first, then adjust code and this guide.

