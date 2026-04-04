Type: CONTRACT
Authority: self

# Group analysis: what each module produces

When you run analysis on a **group**, outputs fall into four **product-facing** classes. The same module id can mean different things depending on whether you run on one transcript or a group.

## Four output classes

| Class | What the user gets | How it is implemented |
| --- | --- | --- |
| **Group charts (registry-backed)** | Aggregate charts under the group run directory, tagged `group_aggregate` in the manifest | [`GROUP_CHART_REGISTRY`](../src/transcriptx/core/analysis/group_charts/registry.py) + [`run_group_aggregate_charts`](../src/transcriptx/core/analysis/group_charts/runner.py) |
| **Group visuals (module-specific path)** | Charts that are **not** produced by `GROUP_CHART_REGISTRY` but still appear in the group run | **wordclouds** — charts written inside [`_aggregate_wordclouds`](../src/transcriptx/core/analysis/aggregation/registry.py) via [`run_group_wordclouds`](../src/transcriptx/core/analysis/wordclouds/analysis.py), tagged `group_aggregate` and **`group_visual_special_path`** |
| **Group data outputs only** | CSV/JSON row bundles (and similar) for the group, **no** group-level chart generator | **temporal_dynamics** — aggregated in [`build_registry`](../src/transcriptx/core/analysis/aggregation/registry.py) but **omitted** from `GROUP_CHART_REGISTRY` (by design; see [`registry` comment](../src/transcriptx/core/analysis/group_charts/registry.py)). Use per-session runs or reports for temporal dashboard charts. |
| **Group composite / blob only** | A JSON blob artifact, not the standard row aggregation + chart pass | **summary** — `output_type="blob"` in the aggregation registry |

## Examples by module

| Module | Class |
| --- | --- |
| stats, sentiment, acts, ner, … | Registry-backed group charts (+ row CSV/JSON) |
| wordclouds | Module-specific group visuals (special path) |
| temporal_dynamics | Data outputs only (no group chart registry entry) |
| summary | Blob-only composite |

## Related docs

- [Group charts: default overview vs gallery](group_charts_default_overview.md) — session, temporal overlay, cross-session speaker, pooled single view
- [Phase 4 outcome table](group_charts_phase4_outcome_table.md) — per-`agg_id` chart decisions
- [Relational pooling model](group_charts_relational_pooling_model.md) — pooled semantics for interactions / contagion
