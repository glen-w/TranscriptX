# ConvoKit analysis (archived)

ConvoKit coordination/accommodation analysis was **archived** due to dependency conflicts with the current stack. The implementation is preserved here for possible re-enablement later.

## Why archived

- **convokit** 3.5.0 requires `numpy>=2.0.0`, `spacy>=3.8.2`, and `thinc>=8.3.0,<8.4.0`.
- These conflict with the project’s current pins (e.g. numpy 1.26.4, spacy 3.7.5, thinc 8.2.5), which are shared with NER and other modules.

See [docs/ROADMAP.md](../docs/ROADMAP.md) for the roadmap note and full dependency details.

## Contents

- `__init__.py` — former `src/transcriptx/core/analysis/convokit/__init__.py` (ConvoKitAnalysis and helpers).
- Tests: [tests/archived/test_convokit.py](../tests/archived/test_convokit.py).

## Re-enabling

1. Resolve convokit/numpy/spacy/thinc version constraints (e.g. upgrade stack or pin an older convokit).
2. Restore the module under `src/transcriptx/core/analysis/convokit/` (copy from this archive).
3. Re-wire: pipeline module registry, analysis config (`ConvokitConfig`), aggregation registry (`_aggregate_convokit`), and `get_convokit()` in `lazy_imports.py`.
4. Re-add the `convokit` optional extra in `pyproject.toml` if desired.
5. Restore capabilities/conftest references to convokit if you use them for testing.
