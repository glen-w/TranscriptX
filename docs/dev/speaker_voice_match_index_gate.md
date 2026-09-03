# Speaker voice match — reference-environment index gate (Stage 9)

Voice matching prefers a rebuildable file matrix under
`speaker_profiles/.cache/voice/indexes/` when present and digest-fresh.
Tree scan remains the degrade path on miss or rebuild failure. No SQLite /
vector-DB dependency.

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

## Measurement (2026-07-23)

Synthetic in-process benchmark via
`scripts/measure_speaker_voice_match_index.py`
(500 profiles × 5 refs = 2500 × 192 float32; 3 queries):

| Metric | Result |
|--------|--------|
| Full-scan matmul | ~0.4 ms (well under 500 ms advisory) |
| Index-resident matmul | ~0.3 ms |
| Estimated matrix RSS | ~1.8 MB (well under +512 MB advisory) |

**Decision:** Ship the digest-keyed file matrix anyway to avoid repeated `.npy`
tree opens on the hot path. Matmul alone does not breach advisories; I/O
amplification on scan does. Prefer file matrix over ANN; SQLite / vector DB
only if the file index still fails a future measured env.

Related: [`speaker_profiles_reference_env_index_gate.md`](speaker_profiles_reference_env_index_gate.md).

## Index layout

```
.cache/voice/indexes/{model_generation_id}/{corpus_digest_dir}/
  meta.json    # voice_ref_index.v1 + embedding_ids / profile_ids
  matrix.npy   # float32 (N, dim)
```

Keyed by `model_generation_id` + `reference_corpus_digest`. Rebuild on miss;
never block analyse on rebuild failure.
