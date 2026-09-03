# Entity sentiment group charts: pooled single view

## Inputs

- **`entity_sentiment_pooled`** on `chart_outcome`, from `aggregate_entity_sentiment_group`.
- `entities`: list of `{entity, entity_type, mentions, mean_sentiment, pos, neu, neg}` from segment-level pooling (global_agg).

## Charts

- `group.entity_sentiment.pooled.top_entities.global` — mentions per entity; mean sentiment values are in the payload for downstream use.

## Semantics

Sentiment is averaged **per mention** (compound/pos/neu/neg summed then divided by mention count) across the pooled corpus.

## Not

- Not inferred from session-level rows alone.
- Fail closed without `entity_sentiment_pooled.entities`.
