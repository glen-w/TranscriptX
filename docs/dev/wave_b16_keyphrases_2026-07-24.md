# Wave B16 — Keyphrases module + wordclouds deepen (2026-07-24)

**Status:** shipped in packaging line **0.8.0**; deep-test hardened **2026-07-24** (suite green; small/large/group analysis probes green).

Split B16: new Language & Meaning module `keyphrases` owns ranked salience; `wordclouds` consumes in-memory upstream rows for keyphrase cloud variants (no second ranker). Module count **50 → 51**. Config ownership invariant **51 / 705 / 16** (721 total).

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
- Session rows via `session_row_from_result` (must include `order_index` — fixed during deep-test)
- Table: `keyphrases_pooled` / `keyphrase_noun_chunk_pool`
- Chart: `keyphrases.phrases.global` (pooled contract: [`group_charts_keyphrases_pooled_contract.md`](../groups/group_charts_keyphrases_pooled_contract.md); `keyphrases_pooled` allowlisted on chart_outcome)
- Pooled noun-chunk cloud via explicit pool into `run_group_wordclouds`; YAKE/KeyBERT deferred

## Speaker policy

Per-speaker keyphrase blocks and keyphrase clouds use the same eligibility helper as wordclouds (`_include_speaker_wordcloud` / `exclude_unidentified_from_speaker_charts`). Global ranks still include text from filtered segments for unidentified speakers when present in `insight_eligibility.filtered_segments` (parity with wordclouds global vs speaker split).

## Group speaker rows

Pooled **per-speaker** group charts/rows for keyphrases are deferred this wave (`speaker_rows` empty); global noun_chunk pool + `keyphrases.phrases.global` chart are the group surfaces.

## Residuals (not this wave)

- Group YAKE / KeyBERT pooling
- Group per-speaker keyphrase rows/charts
- P1 multilingual routing adoption for keyphrase methods

## Related

- Runtime: [`docs/runtime/keyphrases.md`](../runtime/keyphrases.md)
- Group outputs: [`docs/groups/group_analysis_module_outputs.md`](../groups/group_analysis_module_outputs.md)
- Backlog: [`docs/dev/analysis_module_backlog_2026-07-17.md`](analysis_module_backlog_2026-07-17.md)
