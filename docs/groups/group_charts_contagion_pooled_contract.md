Type: CONTRACT
Authority: self

# Contagion group charts: pooled single view (edge-pooled)

See [`group_charts_relational_pooling_model.md`](group_charts_relational_pooling_model.md) (edge-pooled class, parsing, self-edges, display labels, roster semantics, empty payload).

## Inputs

- **`contagion_pooled`** on `chart_outcome`, built during group aggregation (`aggregation/contagion.py`).
- **`schema_version`:** `1`
- **`edges`:** see relational pooling model — one row per directed canonical pair with nested `emotions` counts and optional `total`.

## Chart (v1 default)

- `group.contagion.pooled.top_directed_edges.global` — **top directed edges** by pooled `total` count (sparse, honest under uneven rosters). **Not** a full matrix by default (matrices imply a more complete graph than observed counts justify).

## Session / speaker rows

Existing `session_rows` / `speaker_rows` from contagion aggregation remain for **row writers**; pooled charts use **`contagion_pooled` only**.

## Empty / invalid

- Missing or malformed `contagion_pooled` → no pooled chart (fail closed).
- Valid payload with **no edges** (or all totals zero) → **no pooled chart**, no placeholder.

## Not

- Not a normalized social-network or rate comparison across pairs without an exposure model.
