Type: GUIDE
Authority: advisory

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

## When to add an index

Add a disposable file JSON index under `speaker_profiles/.cache/` only if
reference-env p95 exceeds the advisory targets **and** algorithmic scan counts
show full-tree scans on the hot path. Prefer SQLite only if the file index still
fails advisories on the same reference environment.
