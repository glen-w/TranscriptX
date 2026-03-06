# TranscriptX Test Health Report (pytest)

## Current status (this workspace)

- **Smoke gate**: ✅ passing (`make test-smoke`)
- **Offline safety**: ✅ downloads disabled by default (`TRANSCRIPTX_DISABLE_DOWNLOADS=1`), opt-in with `TRANSCRIPTX_DISABLE_DOWNLOADS=0`
- **Model-heavy tests**: ✅ opt-in only via `TRANSCRIPTX_TEST_MODELS=1` (`@pytest.mark.requires_models`)
- **Quarantined tests**: excluded from `make test-fast`; require reason + sunset (`@pytest.mark.quarantined`)
- **CI ladder (PR)**: Smoke → Contracts → Fast

## CI time budgets (targets)

- `test-smoke` ≤ 2–3 min
- `test-contracts` ≤ 5–8 min
- `test-fast` ≤ 8–12 min
- nightly `integration_core` ≤ 15–25 min

## Test counts (collection)

Collected via `pytest --collect-only`:

- **total collected**: 1534
- **smoke**: 5
- **integration**: 405
- **unit-core (not integration/slow/requires_*)**: 1071
- **requires_models**: 43
- **slow**: 3

## Recommended commands (tiers)

- **CI / required gate**:

```bash
make test-smoke
```

- **Fast local “core” (no integrations, no optional deps)**:

```bash
make test-fast
```

- **Contract tests only**:

```bash
make test-contracts
```

- **Nightly integration core**:

```bash
pytest -m integration_core
```

- **Opt-in model tests**:

```bash
TRANSCRIPTX_TEST_MODELS=1 pytest -m requires_models
```

## Notable failure buckets (non-smoke)

When running beyond `smoke`, the main sources of failures are:

- **Contract drift in non-analysis subsystems**: output services/paths, manifests, state management, web services.
- **Test fixture drift**: missing fixtures or stale expectations (e.g., expected markdown snapshots needed regeneration).
- **Data-extraction utilities**: several extractors depended on shared base helpers that were missing; base extractor now provides `get_speaker_segments`, `safe_float`, `calculate_average`, `calculate_volatility`, `get_most_frequent`.

## What was stabilized/updated in this pass

- **Pytest configuration**:
  - fixed `pytest.ini` to use `[pytest]` section and removed invalid options
  - added/kept marker taxonomy and made model-heavy tests opt-in
- **Smoke suite**:
  - kept CLI smoke, added fast module-level smoke tests for `stats` + `sentiment`
- **Core analysis tests** (contract-based):
  - updated tests for `sentiment`, `stats`, `tics`, `tag_extraction`, `wordclouds`, `interactions` to assert output contracts rather than brittle exactness
  - **Contracts folder**: moved contract tests to `tests/contracts/` (offline + deterministic by path)
  - **NER**: `tests/contracts/test_ner_contracts.py`
  - **Topic modeling**: `tests/contracts/test_topic_modeling_contracts.py`
  - **Emotion**: `tests/contracts/test_emotion_contracts.py` (mocked NRC + model)
- **Contract tests and `requires_models`**: tests under `tests/contracts/` are marked `contract` and are excluded from `requires_models`
- **Integration split**: `integration_core` (stable subset) and `integration_extended` (nightly/manual)
- **Data extraction layer**:
  - aligned data extractors to the `BaseDataExtractor` interface (added missing `__init__`/`extract_data` adapters and shared helpers)

