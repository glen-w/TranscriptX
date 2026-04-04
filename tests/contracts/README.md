# Contract tests (offline + deterministic)

Contract tests assert output shape and minimal schema without relying on models,
external services, or stochastic behavior. They should run under `make test-fast`.

## Checklist (use for every contract test)

- Top-level keys exist
- Types match (`dict`/`list`/`float`/`int`/`str`)
- Nested structures include required keys
- No drift-prone assertions (full text, exact floating values)
- Artifacts (if any): file exists, expected extension, non-empty

## Snapshot strategy

Prefer golden snapshots with normalization helpers:

- `normalize_manifest(obj)` (strip timestamps/bytes, sort artifacts)
- `normalize_stats_txt(text)` (strip dates, normalize whitespace)
- `normalize_csv(path)` (stable headers + row ordering)

See `tests/contracts/normalization.py` for helpers.
