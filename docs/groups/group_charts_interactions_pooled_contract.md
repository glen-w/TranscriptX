# Interactions group charts: pooled single view

See [`group_charts_relational_pooling_model.md`](group_charts_relational_pooling_model.md) (speaker-pooled relational class, dominance rule, `speaker_rows` vs `interactions_pooled`).

## Inputs

- **`interactions_pooled`** on `chart_outcome`, from `aggregate_interactions_group`.
- **`schema_version`:** `1`
- **`speakers`:** list of `{ canonical_speaker_id, display_name, interruptions_initiated, interruptions_received, responses_initiated, responses_received }` — **additive counts only** (summed across transcripts per canonical speaker). **No `dominance_score`** in v1.

## Charts

- `group.interactions.pooled.interruptions_initiated.global` — top speakers by interruptions initiated (pooled corpus).
- `group.interactions.pooled.interruptions_received.global` — top speakers by interruptions received (pooled corpus).

## Session bars

`InteractionsGroupChartGenerator` delegates session summary bars to a curated `GenericNumericGroupChartGenerator` (`total_interactions`, `unique_speakers`, and nullable equity indices `floor_equity_index`, `interruption_asymmetry_index`, `response_latency_fairness_index` per [`generic_field_allowlists.py`](../src/transcriptx/core/analysis/group_charts/generic_field_allowlists.py)). See [`group_charts_interactions_equity_contract.md`](group_charts_interactions_equity_contract.md) for formulas and the semantics-version directional pool gate.

## Empty / invalid

- Fail closed (no pooled charts) if `interactions_pooled` is missing, wrong shape, or no speaker has any positive additive count.
- No placeholder charts when the pooled payload is empty-but-valid.

## Not

- Not inferred from `speaker_rows` in chart code; use `interactions_pooled` only.
