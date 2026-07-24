# Group charts — semantic similarity motifs (B14)

Type: CONTRACT  
Authority: self

## Scope

Cross-session recurring motifs and drift for aggregation id `semantic_similarity`
(prefer member `semantic_similarity_v2` payloads).

## Inputs

- `session_rows` — repetition scalars plus `motif_count`, `recurring_motif_count`,
  `drift_score` (nullable), `included_in_comparison`, provenance key
- `content_rows` / `repetition_rows` — unchanged pair concat contract
- `motif_rows` — group-stable motifs with appearances and trajectory slopes
- `semantic_similarity_pooled` (`schema_version`: `semantic_similarity_pooled.1`) —
  strength/share/presence matrices keyed by `order_index`, truncation metadata,
  `primary_cohort_key`, excluded members, warnings

## Chart generator

Single registry entry: `SemanticSimilarityGroupChartGenerator`

1. Session bars for `total_repetitions` / `unique_patterns` (generic)
2. Null-safe bars for `motif_count` / `recurring_motif_count` / `drift_score`
   (skip null; never coerce unsupported to 0)
3. Motif prevalence (`group.semantic_similarity.motif_prevalence.global`) only when:
   - ≥2 comparable sessions in primary cohort
   - ≥1 recurring motif
   - Strength = cluster size (not match cosine)

## Aggregation semantics

- Compare + centroid match within a comparable provenance cohort
- Include valid-zero motif sessions in the cohort
- TF-IDF backends are `incomparable` (export-only; never cross-match)
- Reject vector-dimension mismatches
- Session `drift_score` = `1 - Jaccard` of group-motif presence vs previous
  comparable session; first session is `null`
- Per-motif `presence_slope` is a separate trajectory metric
- **`group_motif_id`:** `sha1(f"{creating_transcript_id}:{local_motif_id}").hexdigest()[:16]`
  where `creating_transcript_id` is the first session that introduced the motif
- Chart strength uses cluster **size** (and optionally eligible-segment share);
  match cosine is evidence-only. Absent motif in a session is strength `0` on the
  prevalence matrix (not a null `motif_count` coercion)

## Non-goals

- Full embedding re-pool / BERTopic-style refit
- Second registry generator for `semantic_similarity`
- Default overview strip promotion
