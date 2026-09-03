# Stats group charts: pooled single view (totals only)

## Inputs

- **`stats_pooled`**: `total_words`, `total_segments`, `total_duration` summed across session rows in aggregation.

## Chart

- `group.stats.pooled.totals.global` — single bar chart with three categories (words, segments, duration). **Speaker share** is explicitly **out of scope** for this v1 pooled slice.

## Not

- Cross-session speaker charts remain a separate family.
- Fail closed if `schema_version` ≠ 1 or all totals are zero.
