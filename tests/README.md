# TranscriptX tests: how to run locally

## Quick commands (single source of truth)

- `make test-smoke` — CI gate (smoke tests only)
- `make test-fast` — fast core (unit + contracts + pure CLI parsing/help)
- `make test-contracts` — offline contract tests (output shape only)
- `make test-all` — full suite (may be slow)

## CI lane order and time budgets

**PR order**: Smoke → Contracts → Fast

Time budgets (target ceilings):
- `test-smoke` ≤ 2–3 min
- `test-contracts` ≤ 5–8 min
- `test-fast` ≤ 8–12 min
- nightly `integration_core` ≤ 15–25 min

## What “fast core” includes/excludes

**Includes**
- Unit tests under `tests/unit/` or `tests/core/` (no heavy markers)
- Contract tests under `tests/contracts/`
- Pure CLI parsing/help tests (no WhisperX, no HF/OpenAI, no docker exec, no ffmpeg)

**Excludes**
- Integration workflows
- Slow tests
- Model-heavy tests
- Docker, ffmpeg, API/networked tests
- Quarantined tests

## Markers in this repo

- `smoke` — fast, deterministic, CI gate
- `unit` — unit tests for individual functions/classes
- `integration` — workflow/pipeline integration tests
- `integration_core` — stable integration subset for nightly
- `integration_extended` — extended integration suite (nightly/manual)
- `contract` — offline output-shape tests (see `tests/contracts/`)
- `slow` — long-running tests
- `requires_models` — requires downloaded ML models
- `requires_docker` — requires Docker daemon/containers
- `requires_ffmpeg` — requires ffmpeg/ffprobe
- `requires_api` — requires external API access
- `database` — requires DB setup
- `performance` — benchmarks/perf
- `quarantined` — temporarily quarantined tests (must include reason + sunset)

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
