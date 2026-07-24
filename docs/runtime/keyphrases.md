Type: RUNTIME
Authority: self

# Keyphrases (`keyphrases`)

Language & Meaning module (B16) for **method-separated keyphrase ranking**. Visual clouds are owned by `wordclouds` (optional consumer).

## What it is

- Authoritative payload: `schema_id=transcriptx.keyphrases.v1`, `semantics_version=keyphrases_v1`.
- Method-separated ranks under `global_by_method` / `speakers_by_method` — **not** a fused cross-method leaderboard.
- Product primary method: **`noun_chunks`** (spaCy noun chunks on `insight_eligibility.filtered_segments` only; no cross-segment phrases).
- Optional sibling methods: **YAKE**, **KeyBERT** (failure-isolated; skip with typed `skipped_methods` reason codes).
- Each phrase carries `raw_score`, `score_direction`, non-negative `rank_weight` in `[0, 1]`, occurrence/support evidence.

## What it is not

- Not a second topic model (`topic_modeling` / `bertopic`).
- Not NER entities (`ner` / `entity_sentiment`).
- Not filler/`tics` lists.
- Wordclouds do **not** re-rank; they render normalised `rank_weight` from this module when present.

## Language

Noun-chunks path follows spaCy / eligibility language behaviour. YAKE defaults to `yake_lan=en`. KeyBERT uses the configured embedding model (default MiniLM). Unsupported / missing optional packages soft-skip that method only; `usable` reflects the noun_chunks primary path.

## Config

Owned subtree `analysis.keyphrases` (Pydantic pilot `keyphrases`):

| Knob | Default (summary) |
|------|-------------------|
| `enabled_methods` | `noun_chunks`, `yake`, `keybert` |
| `max_phrases` | 40 |
| `min_phrase_tokens` / `max_phrase_tokens` | 1 / 6 |
| `min_occurrences_global` / `min_occurrences_speaker` | 2 / 1 |
| `diversity_jaccard_threshold` | 0.85 |
| `evidence_max_per_phrase` / `evidence_snippet_max_chars` | 3 / 120 |
| `keybert_model_id` | `sentence-transformers/all-MiniLM-L6-v2` |
| `yake_lan` / `yake_n` / `yake_top` / `yake_window_size` | `en` / 3 / 40 / 2 |
| `min_member_sessions` | 2 (group pool gate) |

## Outputs

- `{base}_keyphrases.json` (+ CSV where emitted)
- Insights / Overview extractor for primary `noun_chunks` block
- Charts Gallery wordcloud variants when `wordclouds` runs with upstream payload (`wordcloud.*.keyphrases_*`)
- Group: session rows + `keyphrases_pooled` → chart `keyphrases.phrases.global`; pooled noun-chunk cloud via `keyphrase_noun_chunk_pool` into `run_group_wordclouds`

## Core / extras

- **Noun-chunks** works without the `[keyphrases]` extra (needs spaCy / NLP path as for other language modules).
- **YAKE / KeyBERT:** `pip install -e ".[keyphrases]"` (also included in `.[full]`). Missing packages → `skipped_methods` with `missing_package`; module remains usable if noun_chunks scored.
- Offline / air-gap: disable downloads for KeyBERT Hub fetch; YAKE is local after install.

## Related

- Wave note: [`docs/dev/wave_b16_keyphrases_2026-07-24.md`](../dev/wave_b16_keyphrases_2026-07-24.md)
- Group outputs: [`docs/groups/group_analysis_module_outputs.md`](../groups/group_analysis_module_outputs.md)
- Group pooled chart: [`docs/groups/group_charts_keyphrases_pooled_contract.md`](../groups/group_charts_keyphrases_pooled_contract.md)
- Models: [`docs/runtime/models.md`](models.md)
- Install: [`docs/runtime/installation.md`](installation.md)
