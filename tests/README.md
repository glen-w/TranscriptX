# TranscriptX tests: how to run locally

## Quick commands (single source of truth)

- `pytest` (or `make test-fast`) — **default**: fast lane only (excludes smoke, release_only, integration, integration_core, integration_extended, slow, and requires_* capability markers)
- `make test-smoke` — CI gate (smoke tests only)
- `make test-fast` — same as default `pytest` (fast core)
- `make test-heavy` — heavy profile, excludes quarantined by default
- `make test-heavy-all` — heavy profile including quarantined
- `make test-contracts` — offline contract tests (output shape only)
- `make test-integration` — integration lane (`integration` / `integration_core` / `integration_extended`) excluding external-capability markers
- `make test-release-only` — release-only packaging/install smoke
- `make test-optional` — run only heavy/optional tests (ffmpeg, docker, models, slow, integration)
- `make test-all` — full suite including optional and quarantined (may be slow)

## CI lane order and time budgets

**PR order**: Smoke → Contracts → Fast

Time budgets (target ceilings):
- `test-smoke` ≤ 5 min
- `test-contracts` ≤ 5–8 min
- `test-fast` ≤ 8–12 min
- nightly `integration_core` ≤ 15–25 min

## What “fast core” includes/excludes

**Includes**
- Unit tests under `tests/unit/` or `tests/core/` (no heavy markers)
- Contract tests under `tests/contracts/`
- Web entry point (import + `--help`) tests (no WhisperX, no HF/OpenAI, no docker exec, no ffmpeg)

**Excludes**
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
- `integration` — workflow/pipeline integration tests
- `integration_core` — stable integration subset for nightly
- `integration_extended` — extended integration suite (nightly/manual)
- `contract` — offline output-shape tests (see `tests/contracts/`)
- `slow` — long-running tests
- `requires_models` — requires downloaded ML models
- `requires_docker` — requires Docker daemon/containers
- `requires_ffmpeg` — requires ffmpeg/ffprobe
- `requires_api` — requires external API access
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

- **Fast default (`pytest` / `make test-fast`)**: excludes `quarantined`, `smoke`, `release_only`, `integration`, `integration_core`, `integration_extended`, `requires_ffmpeg`, `requires_docker`, `requires_models`, `requires_api`, `slow`.
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
