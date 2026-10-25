# TranscriptX tests: how to run locally

**Streamlit GUI test assessment:** see [`docs/archive/assessments/streamlit_ui_test_assessment_2026-07-18.md`](../docs/archive/assessments/streamlit_ui_test_assessment_2026-07-18.md) for the surface coverage matrix, doubles-first L1–L3 strategy, heavy-gated AppTest acceptance for seven primary journeys (`make test-gui-acceptance`), residual manual checklist, and the optional `web/` coverage gap-finder (§11). **AppTest remains the structural GUI acceptance lane.** Playwright live-Streamlit E2E (`tests/e2e_gui/`, marker `gui_e2e`) covers the **ten documented key flows** under [docs/workflows/](../docs/workflows/index.md) and is run via `make test-gui-e2e` (skips cleanly when Playwright/Chromium is unavailable; **excluded** from default `pytest` / `make test-fast`).

## Quick commands (single source of truth)

- `pytest` (or `make test-fast`) — **default**: fast lane (excludes smoke, release_only, integration, integration_core, integration_extended, slow, `gui_acceptance`, `gui_e2e`, `browser`, `contract`, and requires_* capability markers).
- `make test-smoke` — CI gate (smoke tests only)
- `make test-fast` — same as default `pytest` (fast core; contracts and Playwright GUI E2E run in their own targets)
- `make test-gui-acceptance` — Streamlit AppTest GUI acceptance journeys (seven primary flows; heavy)
- `make test-gui-e2e` — Playwright live Streamlit GUI E2E only (`tests/e2e_gui`; ten key flows; requires Chromium: `playwright install chromium`)
- `make test-heavy` — heavy profile, excludes quarantined by default
- `make test-heavy-all` — heavy profile including quarantined
- `make test-contracts` — offline contract tests (`contract` marker; output shape only). Not part of fast.
- `make test-integration` — integration lane (`integration` / `integration_core` / `integration_extended`) excluding external-capability markers
- `make test-integration-extended` — `tests/integration` minus `integration_core` (runs nightly after `test-integration-core`)
- `make test-release-only` — release-only packaging/install smoke
- `make test-optional` — run only heavy/optional tests (ffmpeg, docker, models, slow, integration)
- `make test-all` — full suite including optional and quarantined (may be slow)

## CI lane order and time budgets

**PR required gate** (workflow fails only if these fail): `compose-config`, `lint`, `smoke` (`make test-smoke` on Python 3.10 only).

**PR advisory lanes** (`continue-on-error` in `.github/workflows/ci.yml`; still run and report failures): `tests-nlp`, `tests-rag`, `docs` (Sphinx + `docs-gen` drift), `workspaces-theme-c`, `release-checks`. Hosted docs deploy is `pages.yml` on `main`, not the PR gate.

**Install note:** PR `smoke` installs `.[dev]` only. Advisory `tests-nlp` installs `.[dev,nlp,web]`. Smoke still skips spaCy-gated modules unless `[nlp]` is present.

**Nightly:** `.github/workflows/nightly.yml` (schedule `cron` 06:00 UTC + `workflow_dispatch`) runs the broader Gate B lane (`make test-contracts` → `make test-coverage`, which runs fast + contracts with coverage and is the fast gate) plus `make test-integration-core` then `make test-integration-extended` (excluding `requires_docker`; no image pre-build on the nightly runner). Coverage badge refresh follows Nightly, not PR CI.

Time budgets (target ceilings):
- PR `test-smoke` ≤ 5 min
- nightly `test-contracts` ≤ 5–8 min
- nightly `test-fast` ≤ 8–12 min
- nightly `integration_core` ≤ 15–25 min

## What “fast core” includes/excludes

**Includes**
- Unit tests under `tests/unit/` or `tests/core/` (no heavy markers)
- Web entry point (import + `--help`) tests (no WhisperX, no HF/OpenAI, no docker exec, no ffmpeg)

**Excludes**
- Contract tests (`contract` marker; run with `make test-contracts`)
- Integration workflows
- Slow tests
- Model-heavy tests
- Docker, ffmpeg, API/networked tests
- Quarantined tests

Default `pytest` behavior remains the source of truth for the fast local profile; `heavy` exists to make expensive coverage explicit and callable, not to silently redefine unrelated marker semantics.

## Markers in this repo

- `smoke` — fast, deterministic, CI gate
- `unit` — unit tests for individual functions/classes
- `heavy` — excluded from fast local profile due to runtime cost, setup burden, or dependency surface
- `gui_acceptance` — Streamlit AppTest acceptance journeys; excluded from fast; run via `make test-gui-acceptance` (also selected by `make test-heavy` when marked `heavy`)
- `gui_e2e` — Playwright live-Streamlit GUI E2E under `tests/e2e_gui/`; **excluded from default pytest**; dedicated runner `make test-gui-e2e`
- `integration` — workflow/pipeline integration tests
- `integration_core` — stable integration subset for nightly
- `integration_extended` — extended integration suite (nightly/manual)
- `contract` — offline output-shape tests (see `tests/contracts/`)
- `slow` — long-running tests
- `requires_models` — requires downloaded ML models
- `requires_docker` — requires Docker daemon/containers
- `requires_ffmpeg` — requires ffmpeg/ffprobe
- `requires_api` — requires external API access
- `requires_nlp` — requires spaCy (`nlp` extra); excluded from default fast CI lane
- `performance` — benchmarks/perf
- `quarantined` — temporarily quarantined tests (must include reason + sunset)

### Heavy marker policy

- `heavy` is **additive/manual**, not auto-derived from `slow` or `requires_*`.
- `slow` means intrinsically time-consuming.
- `requires_*` markers describe capability/environment contracts.
- A test may be `heavy` without `slow` when setup/dependency burden is the reason.
- A test may be `slow` without `heavy` only as a deliberate, rare, documented exception.
- Integration tests are presumptively `heavy`; keep an integration test out of `heavy` only with a positive documented reason.
- Avoid naked `@pytest.mark.heavy`: include at least one reason marker (`slow`, `requires_*`, `integration`, `integration_core`, `integration_extended`) or document why it belongs in a heavy-designated suite.

## Marker policy matrix

- **Fast default (`pytest` / `make test-fast`)**: excludes `quarantined`, `smoke`, `release_only`, `integration`, `integration_core`, `integration_extended`, `requires_ffmpeg`, `requires_docker`, `requires_models`, `requires_api`, `requires_nlp`, `slow`, `gui_acceptance`, `gui_e2e`, `browser`, `contract`. The expression lives once in the Makefile (`FAST_MARKERS`) and must match `pytest.ini` `addopts` (`tests/utils/test_marker_expression_parity.py`).
- **GUI acceptance (`make test-gui-acceptance`)**: `gui_acceptance` marker; residual manual items in [`docs/dev/gui_acceptance_residual_checklist.md`](../docs/dev/gui_acceptance_residual_checklist.md).
- **GUI E2E (`make test-gui-e2e`)**: `gui_e2e` marker; live Streamlit + Playwright Chromium for the ten documented key flows under `tests/e2e_gui/` (see [docs/workflows/](../docs/workflows/index.md)). Requires `playwright` + `playwright install chromium` (Playwright ships with `[maps]` / `[full]` extras); tests skip when Chromium is unavailable.
- **Smoke lane (`make test-smoke`)**: `tests/smoke` only, requires `smoke` marker, excludes `release_only` and external-capability markers.
- **Integration lane (`make test-integration`)**: `tests/integration` only, includes `integration` or `integration_core` or `integration_extended`, excludes `release_only` and external-capability markers.
- **Release-only lane (`make test-release-only`)**: `tests/release` only, includes `release_only`.
- **Heavy profile (`make test-heavy`)**: includes `heavy`, excludes `quarantined`.
- **Heavy all (`make test-heavy-all`)**: includes all `heavy` tests, including `quarantined`.
- **Optional capability profile (`make test-optional`)**: historical pytest marker bucket (`slow` or `requires_*` or `integration`), independent of explicit `heavy`—not related to runtime “legacy” code paths.

### Marker combination examples

- `@pytest.mark.heavy` + `@pytest.mark.integration` for integration tests that should be excluded from fast local profile.
- `@pytest.mark.heavy` + `@pytest.mark.requires_models` for model-gated expensive tests.
- `@pytest.mark.slow` without `heavy` only if intentionally kept in broad runs and rationale is documented.

## Common environment variables

- `TRANSCRIPTX_TEST_MODELS=1` — opt-in to model-heavy tests
- `TRANSCRIPTX_DISABLE_DOWNLOADS=1` — disable downloads (default behavior)
- `TRANSCRIPTX_DISABLE_DOWNLOADS=0` — opt in to downloads

## Contract test checklist (use for every module)

- Top-level keys exist
- Types match (`dict`/`list`/`float`/`int`/`str`)
- Nested structures have required keys
- No drift-prone assertions (full text, exact floating values)
- Artifacts (if any): file exists, expected extension, non-empty

## CI watchlist (common `make test-fast` failures)

PR CI is **smoke-only** (plus compose + ruff). Contracts / fast run on **Nightly** (see `.github/workflows/nightly.yml`). Failures below are usually **fixture or contract drift**, not a broken venv — fix them before release or when you touch the same surface.

### Config registry / Pydantic pilots

Adding or changing knobs under `src/transcriptx/core/config/models/` triggers a chain of guards:

| Symptom | What to update |
|---------|----------------|
| `test_ownership_invariant_counts` / `test_ownership_snapshot_matches_committed_fixture` | `registry_ownership_snapshot.json`, `test_registry_ownership.py`, `delegation_test_utils.py` |
| `test_pydantic_pilot_*_golden*` / `test_ownership_invariant_unchanged` in `test_*_delegation.py` | Matching `tests/core/config/fixtures/*_golden.json` for the affected pilot |
| `input.recordings_folders` or `output.*` path mismatch | Use portable `<REPO>/data/...` paths in goldens; see [config_architecture.md](../docs/dev/config_architecture.md) |

CI sets isolated `TRANSCRIPTX_DATA_DIR` / `TRANSCRIPTX_OUTPUT_DIR` under `$RUNNER_TEMP`. On a laptop, a repo `.env` can still freeze custom path roots at import time; drift guards patch canonical repo aliases via `with_isolated_config_defaults()` in `delegation_test_utils.py` (see [config_architecture.md](../docs/dev/config_architecture.md)).

**Audio lookup tests:** `find_original_audio_file` may resolve real files under your configured recordings folder unless the test stubs `resolve_file_path` (see `test_file_rename_unit.py`).

**Suite scale (2026-10-22):** ~9239 collected with `-m ""`; default lane ~8860 tests (marker deselects ~378).

Focused local check before pushing config work:

```bash
python -m pytest tests/core/config/test_registry_ownership.py \
  tests/core/config/test_pydantic_bridge_drift.py -q
```

### Streamlit web contracts

| Symptom | Rule |
|---------|------|
| `test_buttons_with_literal_labels_declare_an_icon` | `st.button("Fixed label", ...)` must pass `icon=` using a constant from `transcriptx.web.icons` (no inline `:material/...:` tokens outside `icons.py`) |
| `test_no_inline_material_tokens_outside_the_registry` | Add glyphs to `icons.py`, reference `ic.*` at call sites |

### Other known drift (not always CI-red)

Some characterization goldens still embed **machine-specific** values (absolute paths under the original author’s home directory, pinned `torch_version`, etc.). Those can fail on other hosts or newer PyTorch even when smoke/CI gates are green. Treat them as cleanup debt unless your PR touches the same surface.

Generated docs: the advisory CI `docs` job still runs `make docs-gen` + Sphinx and logs drift or build errors, but it does **not** turn PR CI red. Fix before release or before merging doc/registry changes; Pages (`pages.yml`) rebuilds on `main` when `docs/**` changes.
