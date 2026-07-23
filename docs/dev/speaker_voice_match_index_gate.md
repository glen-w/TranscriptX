Type: GUIDE
Authority: advisory

# Speaker voice match — reference-environment index gate (Stage 9)

Voice matching starts with an in-memory scan of compatible float32 embeddings.
A disposable file index (or ANN) under `speaker_profiles/.cache/voice/indexes/`
may be added **only** after measuring a documented reference environment.

## Reference dataset

- 500 active profiles
- Several thousand trusted voice samples (1–20 per profile)
- 1–5 query excerpts per unidentified occurrence

## Advisory targets (not CI ms gates)

| Hot path | Advisory p95 |
|----------|--------------|
| Analyse one speaker (cached model) | 2 s |
| Full compatible-ref scan | 500 ms |
| Peak RSS over baseline | +512 MB |

## When to add an index

Add a rebuildable `.cache/voice/indexes/` artefact only if reference-env p95
exceeds advisories **and** algorithmic scan counts show full embedding-tree
reads on the hot path. Prefer a file matrix over ANN; SQLite / vector DB only
if the file index still fails. Never a mandatory generic vector-database
dependency.

Related: [`speaker_profiles_reference_env_index_gate.md`](speaker_profiles_reference_env_index_gate.md).
