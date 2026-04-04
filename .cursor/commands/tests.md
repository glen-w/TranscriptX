# Review and Expand Test Suite (# tests)

Review the TranscriptX test suite for health, coverage gaps, and quarantined/skipped tests; then propose and implement targeted expansions (unit, integration, contract) where high leverage is identified.

Execute from the workspace root.

---

## 0. Run backup first (mandatory)

Before doing anything else, run the **backup** custom command (`# backup`). Wait for it to complete, then proceed with the steps below.

---

## 1. Test Artifact Cleanup (optional)

- **Disabled:** Do not run destructive clean-test-artifacts flows; data loss risk. Report that cleanup is disabled unless the user explicitly requests a preview-only pass with a documented script.

---

## 2. Review Phase

### 2.1 Run and summarize current suite

- **Default run (excludes quarantined/heavy):**
  `pytest --co -q` then `pytest -q` (or `pytest -x` to stop on first failure if debugging).
- **Report:** Total collected tests, passed/failed/skipped; any collection errors or import failures.
- **Optional:** `pytest --co -q -m ""` to see full count including quarantined; compare with `tests/TEST_SUITE_ASSESSMENT.md` (~1558 tests noted there).

### 2.2 Structure and markers

- **List test directories** under `tests/`: `analysis`, `contracts`, `core`, `integration`, `io`, `pipeline`, `regression`, `services`, `smoke`, `unit`, `utils`, `web`, etc.
- **Confirm markers** in `pytest.ini`: `smoke`, `unit`, `integration`, `contract`, `slow`, `requires_models`, `requires_docker`, `quarantined`, `integration_core`, `integration_extended`, etc.
- **Default filter:** addopts exclude `quarantined`, `requires_ffmpeg`, `requires_docker`, `requires_models`, `requires_api`, `slow`, `integration` so normal runs stay fast.

### 2.3 Quarantined and skipped tests

- **Read** `tests/TEST_SUITE_ASSESSMENT.md` for the list of quarantined files and reasons (obsolete APIs, removed modules).
- **Identify skipped-at-collection:** e.g. `tests/analysis/test_rules.py` (missing modules). List any others if present.
- **Summarize:** How many tests are quarantined; how many files are skipped at collection; whether any quarantined tests are candidates for update-or-remove.

### 2.4 Coverage and gaps

- **If coverage is available:** Run `pytest --cov=src --cov-report=term-missing -q -m "not quarantined and not requires_ffmpeg and not requires_docker and not requires_models and not requires_api and not slow and not integration"` (or the project's coverage command). Note low-coverage modules or critical paths with no tests.
- **If no coverage run:** Manually compare `src/` packages (e.g. `transcriptx.core`, `transcriptx.io`, `transcriptx.web`, pipeline, services) to `tests/` and list areas with no or few corresponding tests.
- **High-leverage areas** (from assessment): config lifecycle, validation, module registry, transcript loader, pipeline run, state persistence, output builder. Note which of these already have tests and which lack coverage.

---

## 3. Expand Phase

### 3.1 Prioritize expansion targets

- Prefer (in order):
  1) Critical paths with no or minimal tests (config, validation, pipeline, state).
  2) New or refactored code without tests.
  3) Contract tests for output shapes and manifest/artifact invariants.
  4) Stable integration tests (e.g. `integration_core`) that don't require Docker/FFmpeg/models.
- Do **not** re-enable quarantined tests by default; either update them to current APIs (and remove the marker) or leave quarantined and document.

### 3.2 Add or extend tests

- **Unit:** Add or extend tests in `tests/unit/` or the appropriate domain folder (e.g. `tests/core/utils/`, `tests/io/`). Use existing patterns from `tests/unit/test_high_leverage.py`: config, validation, module registry, loader.
- **Integration:** Add or extend in `tests/integration/core/` (e.g. `test_high_leverage_integration.py` style). Use `@pytest.mark.integration_core`, tmp paths, env/monkeypatch; avoid DB or external services when possible.
- **Contract:** Add or extend in `tests/contracts/` for output shape, manifest, and artifact invariants; keep them offline and deterministic.
- **Fixtures:** Reuse fixtures from `tests/conftest.py` and `tests.fixtures.*`; add new fixtures only when necessary and place them in the appropriate conftest or fixture module.

### 3.3 Style and constraints

- Follow existing naming: `test_*.py`, `Test*` classes, `test_*` functions. Use markers consistently (`@pytest.mark.unit`, `@pytest.mark.integration_core`, etc.).
- Prefer small, focused tests; avoid large end-to-end tests unless explicitly requested.
- Ensure new tests are **not** marked `quarantined`, `slow`, or heavy (e.g. `requires_docker`) unless required; default run should include them.

---

## 4. Validation and reporting

- **Re-run default suite** after changes: `pytest -q` (with default addopts). All new/updated tests must pass.
- **Optional:** Run `pytest -m "integration_core" -q` to confirm integration subset passes.
- **Update assessment (optional):** If you added a new test file or a new high-leverage area, add a short note to `tests/TEST_SUITE_ASSESSMENT.md` under "High-leverage tests added" or "Recommendations" so the doc stays accurate.

---

## Execution summary

After running the command, provide:

1. **Review:** Suite status (counts, failures, quarantined/skipped summary), structure/markers, and coverage/gaps summary.
2. **Expansion:** What was added or extended (files and test names), and which high-leverage area each targets.
3. **Result:** Pass/fail of default run and any optional marker run you executed.
