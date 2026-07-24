Type: PRODUCT
Authority: self

> **Archived / superseded.** Historical context only. Current authority: [release_governance.md](../../dev/release_governance.md). Do not treat as live roadmap or support policy.

# Release-hygiene cleanup — 2026-04-01

This document tracks the hygiene-only cleanup pass focused on dead imports, strictly local dead helpers, legacy docs, and ad hoc scripts.

## Scope and exclusions

- Hygiene-only: no changes to core logic, pipeline behavior, IO/storage contracts, analysis semantics, public APIs, CLI entrypoints, web flows, or documented output contracts.
- Excluded from dead-code removal unless safety is unequivocal:
  - Pipeline, IO, storage-contract, manifest/run_results, web entrypoint, CLI entrypoint, registry/plugin, and reflection-driven modules.
  - Any symbol imported for side effects or discovered dynamically.
  - Public-facing or documented utilities, even if they appear unused.
- Excluded from archiving:
  - Any script referenced by `README`, `docs`, `Makefile`, CI/workflows, shell scripts, `pyproject` entrypoints, or release commands.

## Dead imports and strictly local helpers

- Command run: `ruff check src/transcriptx --select F401,F841`
- Result: **no F401/F841 violations reported**; no unused imports or unused locals removed in this pass.
- No helpers were removed; any potential dead-code candidates in core/registry/pipeline paths were intentionally left unchanged.

## Scripts and archiving

Scripts discovered under `scripts/`:

- `scripts/validate_transcript_storage.py`
- `scripts/bench_pipeline_cold_warm.py`
- `scripts/clean_test_artifacts.py`
- `scripts/run_tests_with_timeout.py`
- `scripts/log_code_size.py`
- `scripts/validate_dependencies.py`
- `scripts/validate_registry.py`

References checked:

- `scripts/clean_test_artifacts.py` — used by `Makefile` target `clean-test-artifacts` (kept in place).
- `scripts/bench_pipeline_cold_warm.py` — referenced in `docs/COMPLEXITY_GATES.md` (kept in place).
- `scripts/validate_registry.py` — referenced in `docs/developer_quickstart.md` (kept in place).
- `scripts/log_code_size.py` — self-referenced usage help within the script (treated as active helper, kept in place).

Archived to `archive/scripts/` in this pass:

- `scripts/validate_transcript_storage.py` — no external references found.
- `scripts/run_tests_with_timeout.py` — no external references found.
- `scripts/validate_dependencies.py` — no external references found.

Ambiguous or retained scripts:

- Scripts referenced from docs or `Makefile` were intentionally **not** moved to avoid breaking documented workflows.

## Legacy docs labeled

Legacy/assessment docs discovered:

- `docs/archive/assessment-2026-03-10.md`
- `docs/archive/scikit-learn-upgrade-assessment.md`
- `reports/archive/sidecar_db_assessment.md`
- `tests/TEST_SUITE_ASSESSMENT.md` (test-facing, left unchanged)
- `tests/fixtures/expected_outputs/summary/summary.md` (fixture, left unchanged)

Docs updated with status labels in this pass:

- `docs/archive/assessment-2026-03-10.md` — marked as historical assessment (archived).
- `docs/archive/scikit-learn-upgrade-assessment.md` — marked as historical BERTopic/ sklearn assessment (archived).
- `reports/archive/sidecar_db_assessment.md` — marked as historical sidecar/DB removal assessment (archived).

Docs intentionally left unchanged:

- `tests/TEST_SUITE_ASSESSMENT.md` — treated as test-supporting documentation; not labeled to avoid affecting test expectations.
- `tests/fixtures/expected_outputs/summary/summary.md` — fixture output; left untouched.

## Documentation touchpoints

- No docs or `Makefile` references pointed at the archived scripts; no path updates were required.
- Existing references to active scripts (`bench_pipeline_cold_warm.py`, `clean_test_artifacts.py`, `validate_registry.py`) were preserved as-is.

## Validation

- Linters:
  - `ruff check src/transcriptx --select F401,F841` — **pass**.
- Tests:
  - `make test-smoke` — **[to be run as part of final validation in this pass]**.

## Ambiguities and non-changes

- Any potential dead-code candidates in core pipeline/IO/registry modules were intentionally left unchanged per the hygiene-only scope.
- Historical assessments and design notes were labeled but not rewritten; content remains as historical context.

