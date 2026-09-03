# NER group charts: pooled single view

## Inputs

- Allowlisted chart payload key **`ner_pooled`** on `chart_outcome`, produced by `aggregate_ner_group`.
- Schema: `schema_version` (int), `entity_type_counts` (type → mention count over full corpus), `top_entities` (list of `{entity, entity_type, mentions}`).

## Charts

- `group.ner.pooled.entity_types.global` — bar of entity-type totals (same counting grain as aggregation over all segments).
- `group.ner.pooled.top_entities.global` — top entities by pooled mention count.

## Semantics

Pooled means **one combined corpus**: all group transcripts, same normalization as aggregation (canonicalized entity text, per mention).

## Not

- Not session-by-session comparison.
- Not cross-session speaker identity charts.
- Generators **fail closed** if `ner_pooled` is missing or empty.
