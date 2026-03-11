# TranscriptX Codebase Assessment — 2026-03-10

## Summary Table

| Dimension | Status | Key Finding |
|---|---|---|
| 1. Static Analysis & Type Safety | Needs Attention | 332 ruff violations; 2,111 mypy errors; black 100% compliant |
| 2. Test Health & Coverage | Good | 10/10 smoke pass; 7 fast-suite failures; 6 analysis modules untested |
| 3. Dependency Audit | Needs Attention | 290 outdated packages; `bertopic` extra missing; no CVE scanner in CI |
| 4. Architecture & Code Quality | Needs Attention | 74 files >500 lines; avg complexity B (5.4); `core` imports `cli` (inversion) |
| 5. Documentation & API Surface | Needs Attention | Docstring coverage 68.3% (target 80%); 2 modules undocumented in docs/ |
| 6. Operational & Runtime Readiness | Good | CLI healthy; Docker hygiene good; Alembic CLI unconfigured at root |
| 7. Security & Configuration Hygiene | Needs Attention | Real HF token in `whisperx.env` (gitignored but present locally); no keyring usage |

---

## Dimension 1 — Static Analysis & Type Safety

### Ruff (332 violations)

| Code | Count | Description |
|---|---|---|
| F821 | 166 | Undefined name |
| E402 | 123 | Module-level import not at top of file |
| F401 | 16 | Unused import |
| F403 | 14 | `from module import *` |
| F841 | 3 | Unused local variable |
| E741 | 3 | Ambiguous variable name |
| F405 | 3 | May be from `import *` |
| F811 | 2 | Redefined while unused |
| E721 | 1 | Type comparison with `==` instead of `isinstance` |
| F823 | 1 | Undefined name in `__all__` |

**Top violating files:**

| File | Violations |
|---|---|
| `core/utils/config/system.py` | 62 |
| `cli/main.py` | 25 |
| `core/pipeline/pipeline.py` | 24 |
| `cli/wav_processing_workflow/__init__.py` | 15 |
| `database/models/__init__.py` | 11 |

The 166 F821 "undefined name" violations are the most serious — these can be runtime `NameError` crashes. Many are clustered in `core/utils/config/system.py` (62 violations), suggesting a large file with complex conditional imports or generated code patterns.

The 123 E402 violations reflect intentional deferred imports (optional dependencies, lazy loading), many of which are load-order workarounds rather than style issues.

### Mypy (2,111 errors)

| Error Category | Count |
|---|---|
| Incompatible types in assignment (SQLAlchemy `Column` expressions) | 559 |
| Function missing return type annotation | 266 |
| Function missing type annotation | 137 |
| Missing type annotation on one or more arguments | 90 |
| Missing return statement | 66 |
| `Name "OutputService" is not defined` | 47 |
| Incompatible default for `speaker_map` (None vs dict) | 38 |
| `"object" has no attribute "append"` | 25 |
| Incompatible default for `config` (None vs typed) | 23 |
| Returning `Any` from typed function | 18 |

**Top files with errors:**

| File | Errors |
|---|---|
| `database/models/speaker.py` | 141 |
| `database/models/clustering.py` | 72 |
| `database/models/file_tracking.py` | 65 |
| `database/models/pipeline.py` | 58 |
| `database/models/analysis.py` | 56 |
| `database/models/transcript.py` | 54 |
| `core/analysis/conversation_loops/analysis.py` | 44 |
| `core/viz/mpl_renderer.py` | 42 |

The bulk of mypy errors (559) are SQLAlchemy ORM `Column` type incompatibilities — a known friction between SQLAlchemy 1.x style declarative models and mypy. The 47 `Name "OutputService" is not defined` errors and 13 `Name "PipelineContext" is not defined` errors suggest circular import workarounds with `TYPE_CHECKING` guards that are incompletely applied.

### Black formatting

All 848 files are black-compliant. No action required.

---

## Dimension 2 — Test Health & Coverage

### Smoke suite (CI gate)
All 10 smoke tests pass in 95.6 seconds. The CI gate is healthy.

### Fast test suite
- **1,627 passed, 7 failed, 3 skipped, 2 xfailed** (127 seconds)
- **192 deselected** (slow/model/docker/quarantined exclusions)

**Failures:**

| Test | Error |
|---|---|
| `tests/cli/test_batch_resume.py` (6 tests) | `AttributeError: module 'batch_resume' has no attribute 'PROCESSING_STATE_FILE'` — API changed but tests not updated |
| `tests/database/test_corrections_service.py::test_generate_candidates_force_deletes_old` | `AssertionError: 1 == 0` — stale state assumption in test |

**Expected failures (xfail):**
- `test_pipeline_idempotent_cache_and_artifacts` — pipeline cache_hits reporting known mismatch
- `test_failed_module_creates_failed_run` — mock point changed after refactor

### Quarantined tests
- **85 tests quarantined** across 9 CLI test files, against a baseline of 14
- Current quarantine count (85) is **6× the baseline (14)**, suggesting quarantine is being used as a long-term holding area rather than a temporary measure
- All quarantined tests are in `tests/cli/`, indicating the CLI layer has the most test instability

### Analysis module coverage

| Module | Test Exists |
|---|---|
| `acts` | Yes |
| `affect_tension` | Yes |
| `aggregation` | **No** |
| `bertopic` | **No** |
| `contagion` | Yes |
| `conversation_loops` | Yes |
| `convokit` | **No** |
| `corrections` | **No** |
| `dynamics` | Yes |
| `emotion` | Yes |
| `entity_sentiment` | Yes |
| `highlights` | Yes |
| `interactions` | Yes |
| `ner` | Yes |
| `qa_analysis` | Yes |
| `semantic_similarity` | Yes |
| `sentiment` | Yes |
| `simplified_transcript` | **No** |
| `stats` | Yes |
| `summary` | Yes |
| `temporal_dynamics` | Yes |
| `tics` | Yes |
| `topic_modeling` | Yes |
| `transcript_output` | Yes |
| `understandability` | Yes |
| `voice` | **No** |
| `wordclouds` | Yes |

**6 modules without dedicated test files:** `aggregation`, `bertopic`, `convokit`, `corrections`, `simplified_transcript`, `voice`.

---

## Dimension 3 — Dependency Audit

### Outdated packages
- **290 packages are outdated** out of the installed environment
- Notable major-version lags:
  - `anyio` 3.7.1 → 4.12.1 (major)
  - `av` 14.4.0 → 16.1.0 (two majors)
  - `bcrypt` 4.3.0 → 5.0.0 (major)
  - `cachetools` 5.5.2 → 7.0.5 (major)
  - `cffi` 1.17.1 → 2.0.0 (major)
  - `convokit` 3.5.0 → 4.0.0 (major)
  - `coolname` 2.2.0 → 4.0.0 (major)
  - `dagster` 1.8.13 → 1.12.18
  - `dlt` 1.14.1 → 1.23.0
  - `whisperx` 3.3.0 → 3.8.1

### CVE scanning
`pip-audit` is not installed. No automated CVE scanning is in place. This is a gap for a project with 290+ outdated packages.

### Optional extras status
- Available: `voice`, `emotion`, `nlp`, `ner`, `maps`, `visualization`, `plotly`
- **Missing: `bertopic`** — the `bertopic` analysis module will silently skip in the current environment
- `core_mode = True` by default — optional modules are excluded unless `--no-core` is passed

### Lock file hygiene
- `requirements.txt`, `requirements-lock.txt`, and `constraints.txt` all exist
- The installed package version (`0.42` per `pip show transcriptx`) differs from `pyproject.toml` version (`0.5`), indicating the editable install (`pip install -e .`) may not have been refreshed after the version bump

---

## Dimension 4 — Architecture & Code Quality

### Cross-layer dependency map

```
cli    → app, core, database, io, services, utils
app    → cli, core, database, io          ← app → cli is an inversion
core   → cli, database, io, utils         ← core → cli is an inversion
database → cli, core, utils               ← database → cli is an inversion
io     → cli, core, database, services, utils
services → core, database, io
utils  → core
web    → app, core, database, io, services, utils
```

**670 total cross-layer import instances.**

Three significant architectural inversions are present:
1. `core` imports `cli` — the engine layer should not depend on the CLI layer
2. `app` imports `cli` — the application layer should orchestrate the CLI, not depend on it
3. `database` imports `cli` — the persistence layer should not know about the CLI

These inversions suggest that some utility functions that belong in `core/utils/` or a shared `utils/` layer have been placed in `cli/` modules and are being imported upward.

### File size outliers (>500 lines)

**74 files exceed 500 lines.** Top offenders:

| File | Lines |
|---|---|
| `core/utils/chart_registry.py` | 1,664 |
| `cli/file_selection_utils.py` | 1,590 |
| `core/analysis/wordclouds/analysis.py` | 1,557 |
| `core/pipeline/dag_pipeline.py` | 1,556 |
| `web/app.py` | 1,233 |
| `database/speaker_profiling.py` | 1,221 |
| `cli/main.py` | 1,176 |
| `core/utils/file_rename.py` | 1,126 |
| `cli/file_selection_interface.py` | 1,125 |
| `core/utils/config/analysis.py` | 1,121 |

Files exceeding 1,000 lines are prime refactoring candidates, particularly `chart_registry.py` (1,664), `file_selection_utils.py` (1,590), and `dag_pipeline.py` (1,556).

### Cyclomatic complexity

- **Average complexity: B (5.4)** — acceptable overall
- **94 blocks at rank D or above** (complexity ≥ 10)
- **Highest complexity functions:**

| Function | Rank | Complexity |
|---|---|---|
| `MomentumAnalysis.analyze` | F | 55 |
| `VoiceChartsCoreAnalysis.run_from_context` | F | 63 |
| `DAGPipeline.execute_pipeline` | F | 46 |
| `AdvancedQualityScorer.calculate_quality_score` | D | 30 |
| `EntitySentimentAnalysis.analyze` | E | 32 |
| `SegmentPlayer._play_temp_clip` | E | 36 |
| `SpeakerIdentityService.resolve_speaker_identity` | D | 25 |
| `TranscriptManager.store_transcript` | E | 39 |

Three F-ranked functions (complexity ≥ 30) are critical refactoring targets.

### Dead code (vulture, 80%+ confidence)
20 unused variables detected across 11 files, notably:
- `core/llm/llm_client.py` — 6 unused variables (`system_prompt`, `temperature`, `max_tokens` in two functions), suggesting the LLM client is a stub/placeholder
- `cli/main.py` — 2 unused variables (`print_output_json_path`, `open_browser`)
- `database/models/base.py` and `database/models/file_tracking.py` — unused `mapper` variables (SQLAlchemy event listener pattern)

### Lazy imports / circular import signals
32 files use `lazy_import` or `TYPE_CHECKING`, concentrated in optional-dependency modules (`emotion`, `ner`, `bertopic`, `voice`, `topic_modeling`). This is appropriate for optional extras but suggests some circular import tension in the core pipeline.

---

## Dimension 5 — Documentation & API Surface

### Docstring coverage
- **Actual: 68.3%** vs target of 80%
- Coverage fails the `interrogate` gate (`--fail-under 80`)
- The gap is ~12 percentage points; bringing this to 80% requires adding docstrings to roughly 200–250 additional functions/methods

### Module documentation in docs/
- 25 of 27 analysis modules are mentioned in at least one doc file
- **2 modules not mentioned anywhere in `docs/`:**
  - `affect_tension`
  - `entity_sentiment`

### Version consistency
- `pyproject.toml` version: `0.5`
- `src/transcriptx/__init__.py` version: `0.5` ✓
- `pip show transcriptx` version: `0.42` ← installed version is stale; editable install needs refresh

### README.md
- 92 lines — concise but thin
- Accurately describes architecture (Engine/GUI/CLI) and design principles
- Does not include a quickstart install command or example invocation for new users

### CHANGELOG.md
- 279 lines; current through v0.5 (2026-03-08)
- `[0.5]` and `[0.42]` entries are present and recent

---

## Dimension 6 — Operational & Runtime Readiness

### CLI self-test
- `transcriptx --help` — works correctly ✓
- `transcriptx doctor` — reports config snapshot present, 8 dependencies tracked ✓
- `transcriptx deps status` — all 7 tracked extras show status; `bertopic` is missing ✓

### Optional extras
- `bertopic` extra is missing — the `BERTopic` analysis module will not run
- All other extras are available

### Alembic migration chain
- The `migrations/` directory at the repo root is an unfinished `alembic init` scaffold — `target_metadata = None` and no `alembic.ini` means `alembic history` / `alembic check` cannot be run from the CLI
- The actual migration logic is implemented as custom Python scripts in `src/transcriptx/database/migrations/` (7 scripts, 001–007)
- This is a non-standard pattern: migrations are applied programmatically (via `DatabaseManager`) rather than via Alembic CLI, which means `alembic check` cannot verify schema drift

### Docker
- **Dockerfile quality: Good**
  - Two-stage build (builder / production) ✓
  - `--mount=type=cache` for pip layer caching ✓
  - Non-root user (`transcriptx`) ✓
  - No secrets baked into image ✓
  - Correct `ENTRYPOINT ["transcriptx"]` + `CMD ["interactive"]` ✓
- **docker-compose.yml quality: Good**
  - 3 services: `transcriptx`, `transcriptx-web`, `transcriptx-studio` ✓
  - Health checks on web and studio services ✓
  - Non-root UID/GID passthrough ✓
  - `docker-compose.override.yml` is gitignored and correctly used for local path overrides ✓
  - No HuggingFace token in `docker-compose.yml` ✓

### .env.example
- All referenced env vars are commented out — no live values ✓
- Covers all storage taxonomy paths (library, working, config, backup, database)
- Does **not** include `HF_TOKEN` — consistent with the project's design that HF token is a WhisperX concern, not a TranscriptX concern

---

## Dimension 7 — Security & Configuration Hygiene

### .gitignore audit
| Path | Gitignored |
|---|---|
| `.env` | Yes ✓ |
| `.env.local` | Yes ✓ |
| `docker-compose.override.yml` | Yes ✓ |
| `whisperx.env` | Yes ✓ |
| `processing_state/` | Yes ✓ |
| `transcriptx_data/` | Yes ✓ |
| `.transcriptx/` | Yes ✓ |
| `data/` | Yes ✓ |

All sensitive paths are correctly gitignored.

### Hardcoded secrets
- **`whisperx.env` contains a real HuggingFace token** (`hf_ojgPKNXg...`). This file is gitignored and will not be committed. However, its presence on disk is a risk if the repo is shared or if the machine is compromised. The token should be rotated if it was ever used in CI or shared.
- No hardcoded secrets found in Python source files ✓
- The `tests/regression/test_analysis_only_invariants.py` test actively enforces that `hf_token` does not appear in `core/` or `cli/` source ✓

### Keyring / cryptography usage
- `keyring` is listed as a dependency but **not used in any source file** — it appears to have been added speculatively
- `cryptography` is listed as a dependency but not referenced in source for secrets management
- HuggingFace token flows through environment variables (`.env` / `whisperx.env`), not through a secrets manager or keyring

### Test data hygiene
- `pytest.ini` and test fixtures use synthetic transcript data (generated in `tests/fixtures/`)
- No real transcript data found committed to the repository ✓

---

## Prioritized Remediation Backlog

### P1 — Critical / Breaks Functionality

| ID | Issue | File(s) |
|---|---|---|
| P1-1 | 7 failing fast-suite tests (batch_resume API mismatch; corrections service assertion) | `tests/cli/test_batch_resume.py`, `tests/database/test_corrections_service.py` |
| P1-2 | 166 F821 "undefined name" ruff violations — potential runtime NameErrors | `core/utils/config/system.py` (+25 other files) |
| P1-3 | `bertopic` extra not installed — BERTopic analysis silently unavailable | Environment / `requirements.txt` |
| P1-4 | Installed package version (`0.42`) doesn't match source (`0.5`) — run `pip install -e .` | `pyproject.toml` |
| P1-5 | Real HuggingFace token in `whisperx.env` — rotate token | `whisperx.env` |

### P2 — Needs Attention / Quality Debt

| ID | Issue | File(s) |
|---|---|---|
| P2-1 | 85 quarantined tests (6× baseline of 14) — audit and restore or delete | `tests/cli/` |
| P2-2 | 3 F-ranked functions (complexity 46–63) — refactor | `core/pipeline/dag_pipeline.py`, `core/analysis/dynamics/momentum.py`, `core/analysis/voice/charts_core.py` |
| P2-3 | `core` → `cli` and `database` → `cli` dependency inversions (670 cross-layer imports) | Multiple |
| P2-4 | 6 analysis modules lack dedicated test files | `tests/analysis/` |
| P2-5 | 2,111 mypy errors — prioritize `database/models/` (SQLAlchemy types) and missing return annotations | `database/models/`, multiple |
| P2-6 | Alembic CLI non-functional at repo root — add `alembic.ini` or document custom migration approach | `migrations/`, docs |
| P2-7 | Docstring coverage 68.3% vs 80% target | Multiple |
| P2-8 | 74 files >500 lines — top candidates for decomposition | `core/utils/chart_registry.py`, `cli/file_selection_utils.py`, `core/pipeline/dag_pipeline.py` |
| P2-9 | No CVE scanning (`pip-audit`) in CI/local tooling | CI / `Makefile` |
| P2-10 | `keyring` dependency declared but never used | `pyproject.toml` |

### P3 — Low Priority / Nice to Have

| ID | Issue | File(s) |
|---|---|---|
| P3-1 | 290 outdated packages — prioritize major-version bumps (`anyio`, `bcrypt`, `cffi`, `convokit`) | `requirements.txt` |
| P3-2 | 2 analysis modules (`affect_tension`, `entity_sentiment`) not documented in `docs/` | `docs/` |
| P3-3 | README.md lacks quickstart install command and example invocation | `README.md` |
| P3-4 | `core/llm/llm_client.py` — 6 unused stub variables; LLM client appears incomplete | `core/llm/llm_client.py` |
| P3-5 | 20 unused variables (vulture) — minor cleanup | Multiple |
| P3-6 | Unused `pkg_resources` deprecation warning from `webrtcvad` in smoke tests | Environment |
| P3-7 | `web/streamlit_app.py` (984 lines) appears to be a legacy PoC — consider removing | `web/streamlit_app.py` |
