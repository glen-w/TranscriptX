# Speaker profiles — reference-environment index gate (Stage 8)

Phase 1 keeps longitudinal speaker profiles as portable files under
`data_dir/speaker_profiles/`. A derived file index (or SQLite) may be added
**only** after measuring a documented reference environment.

## Reference dataset

- 500 profiles
- 5 000 links
- 200 managed transcripts

## Reference environment (record when measuring)

Document in the measurement run notes:

- Machine class (CPU, RAM)
- Disk type (SSD / HDD / network)
- Python version
- OS

## Advisory latency targets (not CI ms gates)

| Hot path | Advisory p95 |
|----------|--------------|
| `list_profiles` | 250 ms |
| 50-link appearance resolve | 100 ms |
| Reverse lookup (hashed path) | 50 ms |

Absolute millisecond thresholds are **not** mandatory CI acceptance tests.

## CI / acceptance (non-flaky)

Algorithmic assertions only:

- Files scanned ≤ expected upper bound for the fixture
- Records parsed == N for the fixture
- Rebuild freshness token is byte-identical across two consecutive rebuilds
- Reverse lookup examines O(1) hashed path (or O(index entries) if an index is present), not a full link-tree scan when an index exists

Optional nightly/reference-env jobs may track latency regressions without blocking merges.

## Phase 1.6 analytics pack (2026-07)

Speakers detail builds `AggregationSnapshot` then `build_profile_analytics_pack`
as an in-memory pure transform. **No disposable analytics disk cache** under
`speaker_profiles/.cache/` in v1.

Correctness does not depend on Streamlit TTL for pack payloads (snapshot rebuilt
each Speakers render). `CacheInvalidationSignal` scopes today are
`speaker_profiles`, `speaker_links`, `transcript_summaries` — transcript-library
date edits outside profile mutations may not emit a signal; the next Speakers
render still rebuilds from disk.

Reference-env measurement of snapshot+pack wall time on a many-link fixture is
optional before introducing a versioned disposable analytics cache. Prefer
freshness-key misses for correctness if a cache is added later.

## When to add an index

Add a disposable file JSON index under `speaker_profiles/.cache/` only if
reference-env p95 exceeds the advisory targets **and** algorithmic scan counts
show full-tree scans on the hot path. Prefer SQLite only if the file index still
fails advisories on the same reference environment.
