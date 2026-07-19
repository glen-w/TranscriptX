# Pre-Release Check (# pre-release)

Run a final validation pass before tagging a release (local/Docker distribution; not PyPI).
Execute from the workspace root.

Do not publish, push, tag, or deploy unless explicitly instructed. After completion, summarize readiness and any blocking issues.

Release model for this repo: versioned git tags + Docker Compose image. Do **not** run `twine` / PyPI upload checks.

---

## Blocking Criteria (global)

- Dirty or unexpected git state for the intended release commit (see §0b).
- Any required test failure.
- Any packaging/build failure.
- Any install smoke failure.
- Any environment/config mismatch.
- Any secrets failure or CVE with a published fix.
- Any documented manifest/output contract break.
- Documentation drift on public surfaces is a **warning** (soft gate), not a blocker, unless the user explicitly marks docs as required for this release.

---

## 0. Run backup first (mandatory)

Before doing anything else, run the **backup** custom command (`# backup`) and proceed only after it succeeds. Backup failure is a hard stop for this command.

---

## 0b. Git & CI readiness (mandatory)

- **Working tree:** report `git status --short`. A dirty tree (modified/untracked files that are not explicitly allowed release scratch, e.g. local `.env`) is a **blocker** for tagging. List offending paths.
- **Branch:** report current branch and whether it tracks a remote. Prefer releasing from the project's intended release branch (typically `main` / `master` or a named release branch). Warn if on a throwaway/feature branch unless the user stated a different target.
- **Sync:** `git fetch` (read-only sync of refs) then confirm local HEAD matches the tracked remote (not behind). Being behind remote is a blocker; being ahead is a warning (unpushed commits) unless the release is intentionally local-only.
- **Tag collision:** read `[project].version` from `pyproject.toml`. If `v<version>` (or the project's documented tag form) already exists locally or on the remote, flag as blocker before any new tag.
- **CI on release commit (when GitHub + `gh` available):**
  - Check the latest workflow runs for `HEAD`: `gh run list --branch "$(git branch --show-current)" --limit 10` (or equivalent for the commit SHA).
  - Prefer green required checks on the commit being released. Failed required CI is a blocker; pending CI is a warning; missing `gh`/remote CI is `skipped (unavailable)` with a warning.
  - Do not invent pass/fail from incomplete data—report exactly what was observed.

---

## 1. Tests

- <!-- DISABLED: clean-test-artifacts --apply --yes (delete) - commented out after repeated data loss. -->
- **Interpreter gate first:** record `python --version` and confirm it satisfies `requires-python` from `pyproject.toml` (currently `>=3.10`). Mismatch is a blocker.
- **Source of truth for lanes:** prefer Makefile targets over hand-copied marker strings. Run (in order, adjusting for release target):
  - **Fast required suite:** `make test-fast`
  - **Coverage (same fast filter):** `make test-coverage`
  - **Smoke lane:** `make test-smoke`
  - **Integration lane (if relevant to release target):** `make test-integration`
  - **Release-only packaging lane:** `make test-release-only`
  - **Optional / heavy (non-blocking unless required for this release target):** `make test-optional` / `make test-heavy`
- **Lane alignment audit (required):** compare Makefile test recipes with `pytest.ini` default `addopts` `-m` filter. Flag drift (e.g. markers present in addopts but missing from Makefile, such as `legacy` / `semantic_v2_slow`) as a **warning**, and note which command was actually used. Do not hardcode long `-m` strings in this command when a Makefile target exists.
- **Marker sanity:** run `pytest --markers` once; confirm `optional`, `heavy`, `quarantined`, `smoke`, `release_only`, and the `requires_*` markers used by Makefile targets are declared. (They are declared in this repo; absence of a declared marker used by a make target is a blocker.)
- **Ensure required release tests pass.** Failures in `test-fast`, `test-smoke`, and `test-release-only` are blockers. Integration/optional/heavy follow release-target policy (default: warn unless user says they are in-scope).
- **Review skipped tests.** Confirm every skip has a valid reason (e.g. missing optional dep, platform gate). Flag skips that look like they should be active.
- **Handle flakiness explicitly:** if any test fails, re-run the failed test(s) once before final classification.
  - Passes on re-run: mark as flaky warning.
  - Fails repeatedly: blocker.
  - **Recent pre-release run history source:** read prior flaky nodeids from `artifacts/pre-release/flaky_tests.txt` if present (or prior summaries/logs in `artifacts/pre-release/`).
  - **Non-mutating default policy:** do not create/update flaky history files unless user explicitly enables report-write mode.
  - If a flaky test repeats across runs based on existing history, escalate to blocker; otherwise report as first-observed flaky warning.
- **Coverage reporting:** use `make test-coverage` (consumes `.coveragerc`, writes `coverage.json`). Report overall coverage percentage. Repo gate is **≥ 70%** via `.coveragerc` `fail_under` on that lane—warn (non-blocking) if below or if a different suite was used. If multiple coverage runs were collected, merge before the final number and confirm merge completeness (warning if incomplete).
- **Audit quarantined tests:**
  - Collect inventory: `pytest -m quarantined --collect-only -q`
  - Execute quarantined tests in non-blocking mode: `pytest -m quarantined -q`
  - Report pass/fail counts. Quarantined tests that now pass consistently should be flagged as stale quarantines to remove.
  - Confirm each quarantine has a documented reason; undocumented quarantine is a blocker.
- **Timeboxing:** if a suite appears hung past the configured pytest timeout / Makefile heavy profile (~5+ minutes with no progress), kill the process, report the last output, and classify as blocker for required lanes or warning for optional/heavy. Do not wait indefinitely.

---

## 2. Code Quality

- **Always auto-fix format/lint (required):** apply black + ruff fixes every pre-release run (do not wait for user opt-in).
  - `black` is the canonical formatter for this command unless explicitly changed by project policy.
  - Run in order:
    1. `black src/ tests/ scripts/*.py`
    2. `ruff check src/ tests/ --fix`
    3. Re-verify with `black --check src/ tests/ scripts/*.py` and `ruff check src/ tests/`
  - Use `ruff format` only when the repository is actively migrating formatter policy from Black.
  - Report exactly which files black/ruff changed. Remaining check failures after auto-fix are blockers.
- **Run type checker:** `mypy src/` (with `--ignore-missing-imports` if the project does so).
- **Any mypy type errors are blockers.**
- **Confirm no critical warnings remain.** Summarize any non-zero output from the above tools.

---

## 3. Version & Metadata

- **Version source of truth:** `pyproject.toml` (`[project] version`) is authoritative.
- **Confirm consistency against secondary surfaces:**
  - Package `__init__.py` (`__version__`, if present)—including nested packages that also define `__version__` (e.g. `transcriptx.web`)
  - `README.md` (if a version string is displayed, e.g. "Scope and non-goals (vX.Y)")
- **Flag any mismatch clearly** as a blocker, with `authoritative=...` and `observed=...` values in the report.
- **Ensure changelog is updated** (e.g. `CHANGELOG.md` or `docs/changelog.md`). If changelog exists but the latest entry does not match the current version, flag it.
- **Verify license and author metadata** in `pyproject.toml` are present and look correct.
- **Verify `requires-python`** is present and matches the interpreter gate in §1.

---

## 4. Build & Packaging

- **Build package locally** (artifact quality for Docker/tag installs; not for PyPI upload):
  ```
  python -m build
  ```
  If `build` is not installed, install it first: `pip install build`.
- **Confirm no build errors.**
- **Verify generated artifacts:** Check `dist/` for `.tar.gz` and `.whl` files. Confirm they exist and are non-empty.
- **Inspect packaging contents thoroughly:**
  - **Exclusions** (presence is a blocker): `.transcriptx/`, output dirs (`outputs/`, run artifacts, caches), test fixtures not required at runtime, notebooks (`*.ipynb`), IDE/editor files (`.idea/`, `.vscode/`), local env/secrets (`.env*`, key/token files).
  - **Inclusions** (absence is a blocker when expected for this package): license metadata / `LICENSE` if packaged, runtime package modules under `transcriptx/`, and any non-code runtime data the build is known to ship (templates, default configs, `py.typed` if the project distributes typing markers). Report the checklist used.
  - Inspection methods:
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
  - Verify package import succeeds and is not source-shadowed:
    ```
    python -c "import transcriptx; print(transcriptx.__name__, getattr(transcriptx, '__version__', None), transcriptx.__file__)"
    ```
    `__file__` must point inside `.release-test-env` site-packages.
  - Verify installed version matches authoritative `pyproject.toml` version (blocker on mismatch).
  - Verify entrypoint: `transcriptx --help` (or documented equivalent) and, when available, `transcriptx --version` / version printed by the entrypoint matches `pyproject.toml`.
  - Optional diagnostic only (non-blocking unless explicitly required): `pip install .` to catch `pyproject.toml` install misconfiguration. This does not replace wheel-install smoke.
  Smoke test failure is a blocker.
- <!-- DISABLED: Remove dist/ and *.egg-info - commented out after repeated data loss. --> **Do not delete** `dist/` or `*.egg-info`; report that cleanup is disabled for safety.

---

## 5. Runtime Readiness

- **Confirm `.env.example` is complete:** check every env var reference across bootstrap, settings, and helper/runtime modules (not only `_bootstrap.py`).
  Missing required keys in `.env.example` are blockers.
  Canonical rule: optional env vars should be present in `.env.example` and clearly marked optional; if intentionally omitted to reduce noise, they must be documented in user-facing docs.
- **Dependency/runtime integrity:** run `python -m pip check` and ensure there are no dependency conflicts. Any conflict is a blocker.

---

## 6. Docker (required for launch when Docker is available)

This repo ships via Docker Compose. Prefer project smoke over ad-hoc `docker build`/`docker run`.

- **Canonical check:** `make docker-smoke` (runs `scripts/docker-smoke-test.sh`: compose `transcriptx --help` and `python -m transcriptx.web --help`).
- If that fails, optionally fall back to diagnosing with `docker compose build` / `docker compose run --rm transcriptx-web transcriptx --help` and report the concrete failure.
- **Policy:**
  - Docker not installed/daemon unavailable: `skipped (not available)` — **warning** for launch readiness (not a silent pass).
  - Docker available and smoke fails: **blocker** (Compose is the primary distribution path).
  - Do not require full end-to-end volume/permission demos unless the release target explicitly includes them; if run, permission/output issues are blockers.

---

## 7. Output Sanity Check (required)

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

## 8. Security & Configuration Hygiene

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
- **Scan for dependency vulnerabilities:** Run `pip-audit --progress-spinner off`. If `pip-audit` is missing, install it into the active env (`pip install pip-audit`) then re-run. Report any known CVEs found. CVEs with a published fix are a blocker; those with no fix available are a warning.
- **Check committed large files:** tracked files > 25 MB are warnings; > 100 MB are blockers unless explicitly justified for release assets.

---

## 9. Soft gates / optional high-value checks

- These checks are **non-blocking by default** (warnings) and do not fail release readiness unless the user explicitly elevates them for a target release.
- **Docs / CLI/GUI parity (soft):** validate CLI/GUI entrypoint behavior and public claims against README/docs (`docs/generated/cli.md`, CONTRIBUTING guidance); flag drift as a warning.
- **Coverage merge completeness:** if coverage was collected across multiple pytest invocations, confirm merged report includes all intended suites.
- **Schema drift watch:** explicitly compare current `manifest.json`/`run_results.json` key fields with documented expectations and flag any drift (contract breaks from §7 remain blockers; doc-only wording drift is soft).
- **Makefile ↔ pytest.ini marker drift:** leftover warning detail from §1 lane alignment audit.

---

## Execution Rules

- Do **not** introduce new features.
- Do **not** refactor during pre-release unless fixing a blocking issue.
- Prioritize **stability** over improvements.
- Pre-release is **non-mutating by default**, with one required exception: always apply **black** and **ruff --fix** in §2. Otherwise do not modify tracked files unless explicitly fixing blockers.
- All commands must be run from the workspace root. If a step is run elsewhere, flag it and re-run from root.
- Do **not** modify packaging artifacts (`dist/`, `build/`) except via the explicit build/install steps in this command.
- If any tracked files were modified during checks, list them and justify each change (including black/ruff auto-fixes).
- If a step fails and is fixable with a minimal, safe change (e.g. a missing import, a typo in metadata), fix it and re-run that step. Otherwise, report it as a blocker.
- Public surfaces for docs/readiness decisions are: supported entrypoints, documented import paths, documented outputs/artifacts, and stable user-facing workflows claimed in README/docs.
- After completion, provide a **release readiness summary**:

  | Area | Status |
  |------|--------|
  | Git & CI | clean / dirty / CI fail / skipped |
  | Tests | pass / fail |
  | Coverage | NN% / below threshold |
  | Quarantined tests | NN quarantined / justified / unjustified |
  | Code quality | clean / issues remain |
  | Version & metadata | consistent / mismatch |
  | Build & packaging | success / errors |
  | Runtime readiness | ready / issues / skipped |
  | Docker | success / errors / skipped |
  | Output sanity | verified / issues |
  | Security & hygiene | clean / issues found |
  | Docs (soft) | ok / drift warnings |

  Then:
  - **Blocking issues:** list each with a one-line description.
  - **Warnings (non-blocking):** list any (include soft docs drift here).
  - **Recommended next steps:** what to fix or do before release.
  - **Release readiness:** one of `READY`, `NEEDS FIXES`, or `HIGH RISK`.
