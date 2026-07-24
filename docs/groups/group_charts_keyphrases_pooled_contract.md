Type: CONTRACT
Authority: self

# Keyphrases group charts: pooled single view

## Inputs

- **`keyphrases_pooled`**: noun_chunks rows pooled by `canonical_key` across members
  (sum of `rank_weight`); YAKE/KeyBERT group pooling deferred.

## Chart

- `keyphrases.phrases.global` — top-N pooled noun_chunk phrases by summed
  `rank_weight`.

## Session bars

None for keyphrases (pooled-only family).

## Not

- Per-speaker group rows/charts (deferred).
- YAKE/KeyBERT pooled charts (deferred).
