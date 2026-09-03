# Tics group charts: pooled single view

## Inputs

- **`tics_pooled`**: `total_tics`, `by_tic` (tic label → count) summed from each member transcript’s `global_stats` in aggregation.

## Chart

- `group.tics.pooled.by_tic.global` — bar of pooled tic/filler counts.

## Session bars

Session-level `total_tics` bars remain via `TicsGroupChartGenerator` → curated `GenericNumericGroupChartGenerator`.

## Not

- Fail closed if `by_tic` is empty (no pooled bar).
