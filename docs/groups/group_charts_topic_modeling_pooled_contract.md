# Topic modeling group charts: pooled single view

## Inputs

- **`topic_modeling_pooled`** from `aggregate_topics_group`, after a **group-level LDA** fit on merged preprocessed segments from all transcripts.
- `topics`: `topic_id`, `topic_share` (mean document-topic probability over all segment-documents), `top_terms` (label string).

## Chart

- `group.topic_modeling.pooled.topic_share.global` — bar of mean topic shares for the **group refit** model.

## Semantics (limits)

- Topics are defined by **one LDA fit on the pooled corpus**; topic ids are not comparable to per-transcript standalone runs.
- Requires enough segments (`aggregate_topics_group` minimums); otherwise aggregation returns `None` and no chart is emitted.

## Not

- Not a naive sum of per-session topic tables from different models.
- Fail closed without `topic_modeling_pooled.topics`.
