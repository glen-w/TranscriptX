# Epistemic markers group charts: pooled single view

## Inputs

- **`epistemic_markers_pooled`**: `total_marker_hits`, `by_category` (category → count) summed from member `global_stats.category_counts`; optional descriptive `mean_hits_per_100_tokens`.

## Chart

- `group.epistemic_markers.pooled.by_category.global` — bar of pooled category counts.

## Session bars

Curated session metrics via `EpistemicMarkersGroupChartGenerator` → `GenericNumericGroupChartGenerator` (`total_marker_hits`, rates, shares).

## Not

- Exact token-weighted pool of rates (means are descriptive only).
