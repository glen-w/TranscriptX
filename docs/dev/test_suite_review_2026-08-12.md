Type: ASSESSMENT
Authority: tests/README.md

# TranscriptX test suite review (2026-08-12)

Living assessment of the pytest / Vitest / Playwright testing system.  
**How to run tests:** [`tests/README.md`](../../tests/README.md).  
**Supersedes counts in** [`docs/archive/assessments/TEST_SUITE_ASSESSMENT.md`](../archive/assessments/TEST_SUITE_ASSESSMENT.md) (archived; do not treat as current truth).

**Scope of this pass:** evidence-based audit + prioritized backlog. No remediation in this change set.

---

## 1. Executive verdict

The suite is **large, well-laned, and CI-gated for the fast path**, with strong offline contracts and an explicit GUI AppTest policy. The main risks are not “too few tests,” but **env brittleness and lane gaps**:

1. **NLP half-install kills green lanes** when `spacy` is importable but `en_core_web_md` is missing — smoke, contracts, and many fast-lane analysis tests fail instead of skipping.
2. **`integration_core` nightly** — covered by `.github/workflows/nightly.yml` (`make test-integration-core`); still excluded from PR CI by design.
3. **Web GUI risk is intentionally outside coverage** (`.coveragerc` omits `transcriptx/web/*`) and **outside PR CI** (`gui_acceptance` is manual/heavy); one known AppTest journey failure remains in artifacts.
4. **Soft-skips** in integration-extended DAG tests can hide real pipeline finalization failures.
5. Marker/docs drift is real but mostly P2 (`optional` unused, `browser` not in `pytest.ini`, stale `conftest` comment about `integration_core` in the default suite).

**Strengths:** clear smoke → contracts → fast PR order; Makefile as single command surface; path auto-markers + capability skips; quarantine empty and enforced; Theme C Vitest + Playwright on PR; overall non-web coverage ~83% (above `fail_under=70`).

---

## 2. Live metrics (this review)

Collected on branch tip `227cbe7` (2026-08-12) with `/workspace/.venv` (Python 3.10.20, pytest 9.1.1).

### 2.1 Collection inventory

| Lane / expression | Selected | Notes |
|-------------------|----------:|-------|
| Full (no marker filter) | **8305** | 928 files reporting counts under `tests/` |
| Default `addopts` / `make test-fast` | **8127** (178 deselected) | Matches Makefile ↔ `pytest.ini` |
| Smoke (`tests/smoke` + smoke marker) | **41** | |
| Contracts (`tests/contracts`) | **462** | Also included inside fast (~465 with `contract` marker) |
| `integration_core` | **58** | Not on PR CI |
| Integration lane (`tests/integration` Makefile expr) | **77** | |
| `gui_acceptance` | **7** | Seven journeys; heavy |
| `heavy` (excl. quarantined) | **39** | |
| `release_only` | **1** of 22 under `tests/release` | |
| Optional profile (`slow`/`requires_*`/`integration`) | **92** | |
| `quarantined` / `legacy` | **0** | Quarantine `COUNT=0` |
| `browser` | **3** | Theme C Playwright |
| `performance` | **13** | Manual recipe via `make perf-envelopes`, not CI |

**Tree weight (collected tests by top-level dir):** `core` 3166, `web` 1342, `unit` 952, `analysis` 700, `contracts` 462, `io` 426, `pipeline` 414, `services` 291, … (`smoke` 41, `browser` 3).

**Frontend:** 2 Vitest files (~71 lines) vs 4 TS/TSX source files in the Theme C frontend package — thin but present on CI.

### 2.2 Lane run results (this environment)

| Lane | Result | Duration | vs budget ([tests/README](../../tests/README.md)) |
|------|--------|----------|---------------------------------------------------|
| `make test-smoke` | **9 failed**, 32 passed | ~30s | ≤5 min — under budget; **not green** here |
| `make test-contracts` | **3 failed**, 1 error, 457 passed, 1 skipped | ~20s | ≤5–8 min — under budget; **not green** here |
| Fast + coverage (`make test-coverage` equiv.) | **112 failed**, 8009 passed, 5 skipped, 178 deselected, 1 error | **350s (~5:50)** | ≤8–12 min — under budget; **not green** here |

**Dominant failure classes in this env (fast+coverage):**

| Class | Approx. signal | Meaning |
|-------|----------------|---------|
| Run-cleanup / fingerprint | ~70+ web service tests | `TreeFingerprintError: device change` / `mount` vs `symlink` — Linux/cloud FS assumptions |
| spaCy model missing | ~22+ explicit + cascades | `spacy` importable, `en_core_web_md` absent |
| Emotion-family characterization drift | ~17 | Snapshot/characterization asserts |
| Config path golden drift | few | Goldens encode host-specific `.test_outputs` paths |

**These failures do not prove main is red on GitHub Actions** (`.[dev]` without spaCy typically skips NLP via `importorskip` / extra gates). They **do** prove the suite is brittle on “spaCy present, model absent” and on multi-device / overlay filesystems.

### 2.3 Artifact baselines (Aug 2026)

From [`artifacts/deep_test_20260807_prerelease/`](../../artifacts/deep_test_20260807_prerelease/):

| Lane | Result | Duration |
|------|--------|----------|
| Smoke | 41 passed | 74s |
| Contracts | **2 failed**, 445 passed, 1 skipped | 23s |
| Fast | 7821 passed, 3 skipped, 178 deselected | **450s (7:29)** — within ≤8–12 min |

From [`artifacts/deep_test_gui_heavy.txt`](../../artifacts/deep_test_gui_heavy.txt):

- **1 failed:** `tests/web/gui_acceptance/test_group_run.py::test_group_create_and_run_analysis_group_target`
- Cause: AppTest path not under project/transcripts dir (`canonical_group_member_path` / tmp pytest path)
- 35 passed, 3 skipped

### 2.4 Coverage (fast lane, `.coveragerc`)

| Scope | Coverage |
|-------|----------|
| Overall (web omitted) | **~83%** statements (64036 / 77135) — above `fail_under=70` |
| `core` | 82.9% |
| `services` | 85.4% |
| `io` | 84.1% |
| `app` | 79.5% |
| `export` | 87.5% |
| `utils` | 73.8% |
| `transcriptx/web/*` | **0 files in report** — omitted by policy |

---

## 3. What PR CI protects (and what it does not)

Source: [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml).

```text
PR CI
├── compose-config
├── tests (py 3.10/3.11/3.12): smoke → contracts → fast
├── tests-nlp (py 3.11 + [nlp] + en_core_web_md): smoke-nlp → contracts
├── docs (Sphinx)
├── release-checks (needs above): hygiene, wheel, Docker smoke, …
└── workspaces-theme-c: Vitest + selected pytest + Playwright browser
```

**Protected on every PR:** smoke, contracts, fast, NLP smoke/contracts, Theme C frontend/browser, docs build, release packaging/Docker smoke (after tests).

**Not protected on PR (Makefile-only today; no `schedule:` / cron in workflows):**

- `make test-integration` / `test-integration-core` (58 `integration_core` tests)
- `make test-gui-acceptance` / `test-heavy`
- `make test-optional` (models/docker/ffmpeg/slow)
- Performance envelopes (`make perf-envelopes` is a recipe printer, not a gate)

Docs still describe nightly `integration_core` (≤15–25 min). **No workflow implements that nightly.** That is a process gap, not just a docs nit.

---

## 4. Structure and policy drift

### 4.1 Markers

Declared in [`pytest.ini`](../../pytest.ini). Runtime extras:

| Issue | Detail |
|-------|--------|
| `optional` | Registered; **zero** `@pytest.mark.optional` uses. `make test-optional` selects via `slow`/`requires_*`/`integration` instead |
| `browser` | Registered only in [`tests/browser/conftest.py`](../../tests/browser/conftest.py), not in `pytest.ini` (works via `addinivalue_line`; inconsistent with `--strict-markers` story) |
| `integration` vs `integration_core` | Path auto-mark in [`tests/conftest.py`](../../tests/conftest.py) carefully avoids double-tagging `integration_core`-only tests |
| Stale comment | `conftest` still says default suite **includes** `integration_core`-only tests; **`addopts` explicitly has `not integration_core`** — they are deselected from fast |

Default `addopts` and `make test-fast` marker expressions **match exactly** (verified).

### 4.2 Contracts vs fast

- `contract` is **not** excluded from default/fast.
- CI runs `test-contracts` then `test-fast`, so contract tests run **twice** (~20s redundant cost; ~465 tests).
- README “What fast core includes” listing contracts is **correct** for default pytest; the separate contracts Makefile target is the dedicated gate, not an exclusion from fast.

### 4.3 `collect_ignore` / legacy semantic similarity

Seven v1 files remain on disk and are `collect_ignore`d (cannot be marker-deselected because they import deleted APIs at module level). Active v2 tests live under `tests/analysis/semantic_similarity/`. **Cleanup candidate:** delete ignored v1 files or rewrite; until then keep ignore + comment.

### 4.4 Quarantine

[`tests/quarantine/COUNT`](../../tests/quarantine/COUNT) = **0**. Enforcement tests under `tests/utils/test_quarantine_*.py` remain useful. Policy is healthy.

### 4.5 Autouse fixtures

Root [`tests/conftest.py`](../../tests/conftest.py) autouse: `mock_questionary`, `suppress_logging`, `clean_environment`, plus session spaCy pin. Regression conftest overrides some of these to avoid import chains. Autouse surface is intentional; watch for over-mocking when debugging interactive/CLI-adjacent failures.

### 4.6 Dependency sources

- Primary: `pyproject.toml` `[project.optional-dependencies].dev` (CI uses `pip install -e ".[dev]"`).
- [`requirements-dev.txt`](../../requirements-dev.txt) still lists **`tox>=4.6.0`** with **no `tox.ini`** — dead recommendation.
- Hypothesis warns that `norecursedirs` in `pytest.ini` **replaces** defaults (skips `.hypothesis`); consider extending rather than replacing.

### 4.7 Directory overlap

Duplicate basenames (`test_config.py`, `test_registry.py`, `test_validation.py`, …) map to **different packages** (config vs transcription vs web blocks) — not accidental duplicates. Broader structural overlap remains between `tests/unit/`, `tests/core/`, and `tests/analysis/` (historical growth); reorganization is optional P2, not a correctness bug.

---

## 5. Coverage and risk gaps

### 5.1 Src ↔ tests

| Package | Approx. src `.py` files | Test presence |
|---------|------------------------:|---------------|
| `core` | 764 | Heavy (`tests/core`, `analysis`, `unit`, `pipeline`) |
| `web` | 231 | Heavy tests (~187 files) but **omitted from coverage** |
| `io` | 76 | Solid (`tests/io`) |
| `services` | 70 | Solid |
| `app` | 34 | Moderate (`tests/app`) |
| `export` | 19 | Covered mainly via `tests/utils/test_export_*` + web export service |
| `preprocessing` | stub | Negligible |

Named analysis module with no path-name test hit: **`contextual_emotion`** (worth a follow-up check for alias/coverage under another name).

### 5.2 Web omit policy

[`.coveragerc`](../../.coveragerc) omits `transcriptx/web/*` while ~1342 web tests still execute in fast. Policy reads as “coverage gate focuses on library/core; GUI quality via AppTest + doubles.” That is coherent **if** `gui_acceptance` stays green and residual checklist is walked for releases. Today AppTest is **not** on PR CI, and artifact shows a failing group journey — so the omit is a **blind spot unless process fills it**.

### 5.3 GUI / frontend

- Seven AppTest journeys under [`tests/web/gui_acceptance/`](../../tests/web/gui_acceptance/); residual manual R1–R6 in [`docs/dev/gui_acceptance_residual_checklist.md`](gui_acceptance_residual_checklist.md).
- Policy: Playwright live-Streamlit GUI E2E is a first-class lane under `tests/e2e_gui/` (`gui_e2e`, included in default pytest; Theme C workspaces Playwright remains separate).
- Vitest surface is minimal (lifecycle + index) — acceptable for current Theme C size; expand when frontend grows.

### 5.4 Skip taxonomy (~68 `pytest.skip` call sites; 0 xfail)

| Category | Approx. count | Notes |
|----------|--------------:|-------|
| Missing fixture / file | 23 | Some expected; watch for fixtures that should always exist |
| Other / misc | 20 | Includes “not yet implemented”, optional act types, etc. |
| Soft-fail skip (“Pipeline finalization failed”) | **7** | [`tests/integration/extended/test_dag_pipeline_integration.py`](../../tests/integration/extended/test_dag_pipeline_integration.py) — **treat as P0/P1** |
| Models/NLP | 6 | |
| Docker | 5 | |
| Platform (symlink/FIFO) | 4 | |
| Optional dep / downloads | 2 | |
| Live external | 1 | |

Capability skips via [`tests/capabilities.py`](../../tests/capabilities.py) + `pytest_collection_modifyitems` for `requires_models|docker|ffmpeg` are separate and appropriate.

**P0 pattern:** `_nlp_extra_available()` / `is_extra_available("nlp")` is **import-based** (`spacy` importable ⇒ True) and does **not** require `en_core_web_md`. Smoke then selects spaCy-runtime modules (`highlights`, etc.) and fails hard. Contracts that `importorskip("spacy")` then construct analyzers that call `get_nlp_model()` fail the same way.

---

## 6. Quality sample

### 6.1 CI gate / high-risk

- **Smoke** ([`tests/smoke/test_all_modules_smoke.py`](../../tests/smoke/test_all_modules_smoke.py)): good core-vs-optional split and `_SPACY_RUNTIME_MODULES` allowlist — but NLP readiness check is too weak (package ≠ model).
- **Contracts:** generally follow the README checklist (keys/types); NER contracts mock extractors correctly when setup succeeds; topic/entity contracts still hit live NLP for some paths.
- **GUI group journey:** failure is path-canonicalization vs pytest tmp dirs — harness/product contract issue, not flake noise.
- **Integration extended DAG:** soft-skips on finalization failure hide regressions.

### 6.2 Stratified sample (~24 files across core/web/unit/analysis/contracts/pipeline/io/services)

- Assertion style is mostly structural (`assert key in`, counts, raises) — aligned with contract guidance.
- Long string equality rare in sample; goldens/snapshots used where appropriate.
- Marker hygiene uneven: many files rely on path auto-markers rather than explicit `@pytest.mark.unit`.

### 6.3 Flake / brittleness signals (suite-wide grep)

| Signal | Occurrences | Files |
|--------|------------:|------:|
| `time.sleep` | 22 | 10 |
| Exact float `==` | 304 | 109 |
| `pytest.approx` / `approx(` | 131 uses | — |
| `datetime.now` / `time.time` | 40 | 14 |
| Hardcoded `/tmp` strings | 470 | 119 |

Not all are bugs (fixtures often use `/tmp`). Prefer `tmp_path` / `pytest.approx` when touching floats or host paths; config goldens should avoid machine-specific absolute defaults.

### 6.4 Performance

`performance` marker selects 13 tests; `semantic_v2_slow` exists. Envelope measurement is manual (`scripts/release/perf_envelope_recipe.py`). No automated perf gate in CI — acceptable pre-1.0 if envelopes are maintained in docs.

---

## 7. Prioritized backlog

### P0 — correctness / silent failure / CI truth

1. **Gate NLP on model presence, not only `import spacy`.** Smoke `_nlp_extra_available()`, contract setups, and any module that calls `get_nlp_model()` should skip (or mock) when `en_core_web_md` is missing. Prevents red local/cloud envs and clarifies Core+dev vs `[nlp]` lanes.
2. **Convert DAG “Pipeline finalization failed” soft-skips to failures** (or narrow to a single explicitly documented skip with ticket + sunset). Soft-skip of setup failure masks integration regressions.
3. **Fix or quarantine GUI `test_group_create_and_run_analysis_group_target`** (path under project/transcripts). Until green, do not treat AppTest as release evidence for Groups.

### P1 — protection gaps / portability

4. ~~**Schedule `make test-integration-core`**~~ **Done** — `.github/workflows/nightly.yml` (schedule + `workflow_dispatch`).
5. **Run-cleanup fingerprint tests vs multi-device / overlay FS** — failures (`dev=40 != 39`, `mount` vs `symlink`) indicate env assumptions; make tests tolerate cloud/Linux layouts or document required FS topology.
6. **Decide web coverage policy explicitly in tests README:** either (a) keep omit + require periodic `test-gui-acceptance` evidence, or (b) introduce a thin web coverage/allowlist gate for critical services (e.g. run_cleanup, group_service).
7. **Deduplicate CI contract work** — either exclude `contract` from fast once contracts job is required, or drop the separate job and keep contracts only in fast (prefer keeping the explicit contracts job and excluding from fast to save ~20s and simplify mental model).
8. **Emotion-family characterization + config path goldens** — investigate drift (env vs real); make goldens env-stable.

### P2 — hygiene / maintainability

9. Register `browser` in `pytest.ini`; remove or start using `optional` mark; fix stale `conftest` comment about `integration_core` in default suite.
10. Delete or rewrite the seven `collect_ignore` semantic_similarity v1 files.
11. Drop unused `tox` from `requirements-dev.txt` or add a real `tox.ini`.
12. Extend `norecursedirs` instead of replacing pytest defaults (Hypothesis warning).
13. Expand Vitest only as Theme C frontend surface grows; keep Streamlit Playwright deferred per policy unless residual checklist stays release-blocking.
14. Spot-check `contextual_emotion` for missing dedicated tests.
15. Prefer `pytest.approx` over bare float equality when editing the ~109 files with exact float asserts.

---

## 8. Recommended follow-ups (out of scope here)

- Remediation PR for P0 items 1–3.
- Nightly workflow PR for `integration_core` (+ optional GUI acceptance on a schedule). → **Nightly `integration_core` shipped** (`.github/workflows/nightly.yml`); GUI acceptance schedule still optional.
- Optional: refresh deep_test artifact pack after NLP-gate and cleanup-portability fixes for a clean baseline.

---

## 9. Method notes

- Live `pytest --collect-only` per lane; Makefile/CI/README/`conftest`/`pytest.ini` cross-read.
- Executed smoke, contracts, and fast+coverage in this environment; compared to `artifacts/deep_test_20260807_*` and `deep_test_gui_heavy.txt`.
- Skip/marker/flake greps; stratified assertion sample; src↔test map; coverage JSON package rollup.
- Did **not** treat archived `TEST_SUITE_ASSESSMENT.md` counts as authoritative.
