Type: PRODUCT
Authority: self

# Wave B16 — Keyphrases module + wordclouds deepen (2026-07-24)

Split B16: new Language & Meaning module `keyphrases` owns ranked salience; `wordclouds` consumes in-memory upstream rows for keyphrase cloud variants (no second ranker).

## Contract

- `schema_id`: `transcriptx.keyphrases.v1`
- `semantics_version`: `keyphrases_v1`
- Method-separated ranks (`global_by_method` / `speakers_by_method`); product primary = `noun_chunks`
- Fields: `usable`, `evaluation_state`, `methods_run`, typed `skipped_methods`, `raw_score` + `score_direction` + `rank_weight`
- Candidates only from `insight_eligibility.filtered_segments` (no cross-segment phrases)
- Owned phrase_quality adapter (not theme APIs as public keyphrase API)

## Wordclouds consumer

- `optional_dependencies=["keyphrases"]` (hard deps unchanged — existing clouds do not fail when keyphrases skips)
- `run_from_context` captures keyphrases payload; passed through `analyze()` → `run_all_wordclouds` → `emit_keyphrase_wordclouds`
- Single-transcript `skipped_variants` manifest via `wordclouds_skipped_variants.json`
- `WordcloudTerms.ngram` may be `null`; terms carry `kind="keyphrase"` and upstream provenance

## Group

- Pool by `canonical_key` (never concat-reparse); min member-session support
- Table: `keyphrases_pooled` / `keyphrase_noun_chunk_pool`
- Chart: `keyphrases.phrases.global`
- Pooled noun-chunk cloud via explicit pool into `run_group_wordclouds`; YAKE/KeyBERT deferred

## Packaging

- Optional extra `keyphrases` (yake, keybert); noun_chunks uses existing NLP
- KeyBERT: no implicit downloads (`local_files_only` / offline env)
