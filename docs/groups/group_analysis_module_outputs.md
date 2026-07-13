Type: CONTRACT
Authority: self

# Group analysis: what each module produces

When you run analysis on a **group**, outputs fall into five **product-facing** classes. The same module id can mean different things depending on whether you run on one transcript or a group.

## Five output classes

| Class | What the user gets | How it is implemented |
| --- | --- | --- |
| **Group charts (registry-backed)** | Aggregate charts under the group run directory, tagged `group_aggregate` in the manifest | [`GROUP_CHART_REGISTRY`](../src/transcriptx/core/analysis/group_charts/registry.py) + [`run_group_aggregate_charts`](../src/transcriptx/core/analysis/group_charts/runner.py) |
| **Group visuals (module-specific path)** | Charts that are **not** produced by `GROUP_CHART_REGISTRY` but still appear in the group run | **wordclouds** — charts written inside [`_aggregate_wordclouds`](../src/transcriptx/core/analysis/aggregation/registry.py) via [`run_group_wordclouds`](../src/transcriptx/core/analysis/wordclouds/analysis.py), tagged `group_aggregate` and **`group_visual_special_path`** |
| **Group data outputs only** | CSV/JSON row bundles (and similar) for the group, **no** group-level chart generator | **temporal_dynamics** — aggregated in [`build_registry`](../src/transcriptx/core/analysis/aggregation/registry.py) but **omitted** from `GROUP_CHART_REGISTRY` (by design; see [`registry` comment](../src/transcriptx/core/analysis/group_charts/registry.py)). Use per-session runs or reports for temporal dashboard charts. Also blob-adjacent text modules such as **llm_summary** / **narrative_summary** (blob collect) and **llm_speaker_summary** (speaker rows). |
| **Group composite / blob only** | A JSON blob artifact, not the standard row aggregation + chart pass | **summary**, **llm_summary**, **narrative_summary** — `output_type="blob"` in the aggregation registry |
| **Excluded (`supports_group=false`)** | Not offered for group runs (defaults, picker, readiness). May still run as an auto-added **dependency** of a supported module on each member | `voice_contours`, `corrections`, `insight_eligibility`, `transcript_output`, `simplified_transcript` |

## Examples by module

| Module | Class |
| --- | --- |
| stats, sentiment, acts, ner, … | Registry-backed group charts (+ row CSV/JSON) |
| wordclouds | Module-specific group visuals (special path) |
| temporal_dynamics | Data outputs only (no group chart registry entry) |
| summary, llm_summary, narrative_summary | Blob-only composite |
| llm_action_items, insights, semantic_similarity*, voice_mismatch/tension/fingerprint | Rows (+ charts where registered) |
| prosody (from voice_features / voice_charts_core / prosody_dashboard) | Registry-backed via existing `prosody` agg |
| corrections, insight_eligibility, transcript_output, simplified_transcript, voice_contours | Excluded (`supports_group=false`) |

\* `semantic_similarity`, `semantic_similarity_advanced`, and `semantic_similarity_v2` share one aggregation entry.

## Related docs

- [Group charts: default overview vs gallery](group_charts_default_overview.md) — session, temporal overlay, cross-session speaker, pooled single view
- [Phase 4 outcome table](group_charts_phase4_outcome_table.md) — per-`agg_id` chart decisions
- [Relational pooling model](group_charts_relational_pooling_model.md) — pooled semantics for interactions / contagion
