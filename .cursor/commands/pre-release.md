# Pre-Release Check (# pre-release)

Run a final validation pass before tagging or publishing a release.
Execute from the workspace root.

Do not publish, push, or deploy unless explicitly instructed. After completion, summarize readiness and any blocking issues.

---

## Blocking Criteria (global)

- Any required test failure.
- Any packaging/build failure.
- Any install smoke failure.
- Any environment/config mismatch.
- Any secrets failure or CVE with a published fix.
- Any documented manifest/output contract break.
- Any documentation drift in public surfaces.

---

## 0. Run backup first (mandatory)

Before doing anything else, run the **backup** custom command (`# backup`) and proceed only after it succeeds. Backup failure is a hard stop for this command.

---

## 1. Tests

- <!-- DISABLED: clean-test-artifacts --apply --yes (delete) - commented out after repeated data loss. -->
- **Define release-profile pytest commands** and run them in this order:
  - **Fast required suite:** `pytest -m "not optional and not heavy and not quarantined"`
  - **Optional suite (non-blocking unless required for this release target):** `pytest -m "optional and not quarantined"`
  - **Heavy suite (run only if relevant to release target):** `pytest -m "heavy and not quarantined"`
  - **Marker presence detection:** run `pytest --markers` and verify `optional`, `heavy`, and `quarantined` markers are declared.
  - **Fallback behavior when markers are absent:**
    - If `optional` and/or `heavy` are missing, run required tests as `pytest -m "not quarantined"` and mark optional/heavy suites as `skipped (marker not defined)`.
    - If `quarantined` is missing, run required tests as plain `pytest`; quarantine audit becomes `skipped (marker not defined)` and must be reported.
    - Always report detected markers and the exact fallback command used.
- **Ensure required release tests pass.** Any failure in required suites is a blocker; optional/heavy suite failures follow the release-target policy above.
- **Review skipped tests.** Confirm every skip has a valid reason (e.g. missing optional dep, platform gate). Flag skips that look like they should be active.
- **Handle flakiness explicitly:** if any test fails, re-run the failed test(s) once before final classification.
  - Passes on re-run: mark as flaky warning.
  - Fails repeatedly: blocker.
  - **Recent pre-release run history source:** read prior flaky nodeids from `artifacts/pre-release/flaky_tests.txt` if present (or prior summaries/logs in `artifacts/pre-release/`).
  - **Non-mutating default policy:** do not create/update flaky history files unless user explicitly enables report-write mode.
  - If a flaky test repeats across runs based on existing history, escalate to blocker; otherwise report as first-observed flaky warning.
- **Run coverage on the same required release test set** (not a different suite):
  ```
  pytest -m "not optional and not heavy and not quarantined" --cov=src/transcriptx --cov-report=term-missing --cov-report=xml
  ```
  If optional/heavy suites are run with coverage separately, merge coverage data before reporting final coverage (e.g. combine `.coverage*` files and produce one final report).
  Confirm downstream tooling (CI/reporting) consumes `coverage.xml`; if not consumed, flag as warning.
  Report the overall coverage percentage. Warn (non-blocking) if below 60%.
- **Audit quarantined tests:**
  - Collect inventory: `pytest -m quarantined --collect-only -q`
  - Execute quarantined tests in non-blocking mode: `pytest -m quarantined -q`
  - Report pass/fail counts. Quarantined tests that now pass consistently should be flagged as stale quarantines to remove.
  - Confirm each quarantine has a documented reason; undocumented quarantine is a blocker.

---

## 2. Code Quality

- **Default mode is non-mutating (required):**
  - `black` is the canonical formatter for this command unless explicitly changed by project policy.
  - `black --check src/ tests/ scripts/*.py`
  - `ruff check src/ tests/`
  - Use `ruff format --check` only when the repository is actively migrating formatter policy from Black.
- **Repair mode (explicit opt-in only):** only if user explicitly requests auto-fix for blockers, run:
  - `black src/ tests/ scripts/*.py`
  - `ruff check src/ tests/ --fix`
  Then re-run check-only commands and report exactly what changed.
- **Run type checker:** `mypy src/` (with `--ignore-missing-imports` if the project does so).
- **Any mypy type errors are blockers.**
- **Confirm no critical warnings remain.** Summarize any non-zero output from the above tools.

---

## 3. Version & Metadata

- **Version source of truth:** `pyproject.toml` (`[project] version`) is authoritative.
- **Confirm consistency against secondary surfaces:**
  - Package `__init__.py` (`__version__`, if present)
  - `README.md` (if a version string is displayed, e.g. "Scope and non-goals (vX.Y)")
- **Flag any mismatch clearly** as a blocker, with `authoritative=...` and `observed=...` values in the report.
- **Ensure changelog is updated** (e.g. `CHANGELOG.md` or `docs/changelog.md`). If changelog exists but the latest entry does not match the current version, flag it.
- **Verify license and author metadata** in `pyproject.toml` are present and look correct.

---

## 4. Documentation

- **Run `/docs` custom command** and require explicit success criteria:
  - Documented import paths resolve against current code.
  - All code examples/entrypoint examples match current behavior.
  - Primary/secondary entrypoints in docs align with actual supported entrypoints.
  - Output artifact docs include `manifest.json`, `run_results.json`, and currently supported report artifacts.
  - Any drift found is listed with file path and required fix.
  - `/docs` must return structured output listing:
    - updated files
    - drift findings
  `/docs` failures are blockers for release.

---

## 5. Build & Packaging

- **Build package locally:**
  ```
  python -m build
  ```
  If `build` is not installed, install it first: `pip install build`.
- **Confirm no build errors.**
- **Verify generated artifacts:** Check `dist/` for `.tar.gz` and `.whl` files. Confirm they exist and are non-empty.
- **Inspect packaging contents thoroughly:** inspect both sdist and wheel file lists and explicitly verify exclusion of:
  - `.transcriptx/`
  - output directories (`outputs/`, run artifacts, caches)
  - test fixtures not required at runtime
  - notebooks (`*.ipynb`)
  - IDE/editor files (`.idea/`, `.vscode/`, workspace files)
  - local environment files/secrets (`.env*`, key/token files)
  - Suggested inspection methods:
    - sdist: `tar tzf dist/*.tar.gz`
    - wheel: select a concrete wheel filename first (for example via `ls dist/*.whl`), then run `python -m zipfile -l dist/<wheel-file>.whl`
- **Check artifact size sanity:** flag unusually large wheel/sdist artifacts as blockers if size suggests accidental data inclusion.
  - Default thresholds (override if project policy defines different limits):
    - wheel (`.whl`) > 50 MB => blocker
    - sdist (`.tar.gz`) > 100 MB => blocker
- **Install smoke test in clean environment (required):**
  - `.release-test-env` must be freshly recreated for each pre-release run (do not reuse an existing venv).
  - Create explicit clean venv: `python -m venv .release-test-env`
  - Activate it and install built wheel from `dist/`.
  - Verify package import succeeds (`python -c "import transcriptx; print(transcriptx.__name__)"`).
  - Verify import is from installed environment, not local source shadowing (e.g. inspect `transcriptx.__file__` and ensure it points inside `.release-test-env` site-packages).
  - Verify basic entrypoint works (`transcriptx --help` or documented equivalent).
  - Optional diagnostic only (non-blocking unless explicitly required): `pip install .` to catch `pyproject.toml` install misconfiguration. This does not replace wheel-install smoke.
  Smoke test failure is a blocker.
- <!-- DISABLED: Remove dist/ and *.egg-info - commented out after repeated data loss. --> **Do not delete** `dist/` or `*.egg-info`; report that cleanup is disabled for safety.

---

## 6. Runtime Readiness

- **Confirm `.env.example` is complete:** check every env var reference across bootstrap, settings, and helper/runtime modules (not only `_bootstrap.py`).
  Missing required keys in `.env.example` are blockers.
  Canonical rule: optional env vars should be present in `.env.example` and clearly marked optional; if intentionally omitted to reduce noise, they must be documented in user-facing docs.
- **Dependency/runtime integrity:** run `python -m pip check` and ensure there are no dependency conflicts. Any conflict is a blocker.

---

## 7. Docker (if applicable)

Only run this section if a `Dockerfile` or `docker-compose.yml` exists in the workspace root.

- **Build Docker image:** `docker build -t transcriptx:latest .`
- **Confirm the image runs:** `docker run --rm transcriptx:latest` (or the appropriate command for the project's entrypoint).
- **Verify volume mounting and outputs** behave as expected if applicable (no permission errors, output written to expected location).
- **Docker expectation policy:**
  - If Docker is not installed/available, mark Docker as `skipped (not installed)`.
  - Treat Docker failures as blockers only when Docker is part of the release target. Otherwise warn.

---

## 8. Output Sanity Check (required)

- **Canonical sample source:** use the repository's designated canonical sample transcript fixture (documented path in README/docs). If none is documented, use one agreed fixture under `tests/fixtures/` and report the exact path used.
- **Run one canonical sample transcript through the primary supported pipeline** and verify required outputs.
- **Required artifacts must exist (minimal published set):**
  - `manifest.json`
  - `run_results.json`
  - the report artifact required by the selected pipeline profile, as documented (`report.md` or `report.json` when required)
  - primary tabular/statistical output expected by the profile (CSV/JSON summary as documented)
- **Required artifact directories must exist:** missing expected output directories are blockers.
- **Verify canonical naming and directory structure** match documented conventions (including base-derived prefixes and expected subdirectories).
- **Validate manifest/report contract stability:** ensure key fields in `manifest.json`/`run_results.json` remain present and consistent with documented schema expectations from canonical contract sources (schema/golden files if present, otherwise README/docs).
- **Filesystem invariant:** no unexpected top-level files/directories should be created by the sanity run.
- <!-- DISABLED: Clean up test run artifacts (delete) - commented out after repeated data loss. --> Do **not** delete test run artifacts; report that cleanup is disabled for safety.

---

## 9. Security & Configuration Hygiene

- **Run secrets check resiliently:**
  - Ensure `scripts/secrets_check.sh` exists and is executable before running it.
  - If missing or not executable, fail this step clearly as a blocker.
  - Then run: `bash scripts/secrets_check.sh`. Any failure (tracked `whisperx.env`, committed HuggingFace tokens) is a blocker.
- **Verify `.gitignore` covers critical paths.** Confirm the following are excluded:
  - `.env`
  - `.env.*`
  - `whisperx.env`
  - `processing_state/`
  - `transcriptx_data/`
  - `outputs/`
  - `.transcriptx/`
  - `__pycache__/`
  - `.pytest_cache/`
  - `.mypy_cache/`
  - `.ruff_cache/`
  - `build/`
  - `dist/`
  - `*.egg-info/`
  - `*.key`
  - notebook and IDE noise as applicable (`.ipynb_checkpoints/`, `.idea/`, `.vscode/`)
  Flag any missing critical pattern as a blocker.
- **Scan for dependency vulnerabilities:** Run `pip-audit --progress-spinner off`. Report any known CVEs found. CVEs with a published fix are a blocker; those with no fix available are a warning.
- **Check committed large files:** tracked files > 25 MB are warnings; > 100 MB are blockers unless explicitly justified for release assets.

---

## 10. Optional High-Value Checks

- These checks are non-blocking by default and do not affect release readiness unless explicitly marked otherwise for a target release.
- **CLI/GUI docs parity:** validate CLI/GUI entrypoint behavior is consistent with README/docs claims; flag drift.
- **Coverage merge completeness:** if coverage was collected across multiple pytest invocations, confirm merged report includes all intended suites.
- **Schema drift watch:** explicitly compare current `manifest.json`/`run_results.json` key fields with documented expectations and flag any drift.

---

## Execution Rules

- Do **not** introduce new features.
- Do **not** refactor during pre-release unless fixing a blocking issue.
- Prioritize **stability** over improvements.
- Pre-release is **non-mutating by default**: do not modify tracked files unless explicitly fixing blockers (or user requests repair mode).
- All commands must be run from the workspace root. If a step is run elsewhere, flag it and re-run from root.
- Do **not** modify packaging artifacts (`dist/`, `build/`) except via the explicit build/install steps in this command.
- If any tracked files were modified during checks, list them and justify each change.
- If a step fails and is fixable with a minimal, safe change (e.g. a missing import, a typo in metadata), fix it and re-run that step. Otherwise, report it as a blocker.
- Public surfaces for docs/readiness decisions are: supported entrypoints, documented import paths, documented outputs/artifacts, and stable user-facing workflows claimed in README/docs.
- After completion, provide a **release readiness summary**:

  | Area | Status |
  |------|--------|
  | Tests | pass / fail |
  | Coverage | NN% / below threshold |
  | Quarantined tests | NN quarantined / justified / unjustified |
  | Code quality | clean / issues remain |
  | Version & metadata | consistent / mismatch |
  | Documentation | aligned / drift found |
  | Build & packaging | success / errors |
  | Runtime readiness | ready / issues / skipped |
  | Docker | success / errors / skipped |
  | Output sanity | verified / issues |
  | Security & hygiene | clean / issues found |

  Then:
  - **Blocking issues:** list each with a one-line description.
  - **Warnings (non-blocking):** list any.
  - **Recommended next steps:** what to fix or do before release.
  - **Release readiness:** one of `READY`, `NEEDS FIXES`, or `HIGH RISK`.
