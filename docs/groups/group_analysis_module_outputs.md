Type: CONTRACT
Authority: self

# Group analysis: what each module produces

When you run analysis on a **group**, outputs fall into four **product-facing** classes. The same module id can mean different things depending on whether you run on one transcript or a group.

All registered pipeline modules support group runs (`supports_group=true`) and have an aggregation entry. BERTopic (`bertopic`) is a default-installed module (packages in base deps for now; see [installation.md](../runtime/installation.md) install-profile note) with group aggregation that **refits from pooled source segments** (member topic IDs are not joined across fits).

## Four output classes

| Class | What the user gets | How it is implemented |
| --- | --- | --- |
| **Group charts (registry-backed)** | Aggregate charts under the group run directory, tagged `group_aggregate` in the manifest | [`GROUP_CHART_REGISTRY`](../src/transcriptx/core/analysis/group_charts/registry.py) + [`run_group_aggregate_charts`](../src/transcriptx/core/analysis/group_charts/runner.py) |
| **Group visuals (module-specific path)** | Charts that are **not** produced by `GROUP_CHART_REGISTRY` but still appear in the group run | **wordclouds** — charts written inside [`_aggregate_wordclouds`](../src/transcriptx/core/analysis/aggregation/registry.py) via [`run_group_wordclouds`](../src/transcriptx/core/analysis/wordclouds/analysis.py), tagged `group_aggregate` and **`group_visual_special_path`** |
| **Group data outputs only** | CSV/JSON row bundles (and similar) for the group, **no** group-level chart generator | **temporal_dynamics**, **insight_eligibility**, **voice_contours**, **llm_speaker_summary**, **contextual_emotion**, **fine_grained_emotion**, **llm_custom_qa** — aggregated in [`build_registry`](../src/transcriptx/core/analysis/aggregation/registry.py) but **omitted** from `GROUP_CHART_REGISTRY` (by design; see [`registry` comment](../src/transcriptx/core/analysis/group_charts/registry.py); `llm_custom_qa` group chart pending v2 loader). Use per-session runs or reports for member charts where applicable. |
| **Group composite / blob only** | A JSON blob artifact, not the standard row aggregation + chart pass | **summary**, **llm_summary**, **narrative_summary**, **transcript_output** — `output_type="blob"` in the aggregation registry. For **llm_summary** / **llm_speaker_summary**, group finalize may additionally run [group LLM synthesis](group_llm_synthesis_contract.md) (generation-scoped ACTIVE/COMMIT under `.group_llm_synthesis/`). |

## Examples by module

| Module | Class |
| --- | --- |
| stats, sentiment, acts, ner, lexical_diversity, simplified_transcript, transcript_quality, epistemic_markers, politeness, keyphrases, topic_shift, … | Registry-backed group charts (+ row CSV/JSON); **transcript_quality** pools only within matching ASR provenance cohorts (see below); **keyphrases** pools noun_chunks by `canonical_key` (YAKE/KeyBERT deferred) with chart `keyphrases.phrases.global` |
| wordclouds | Module-specific group visuals (special path); includes pooled **keyphrase_noun_chunks** cloud when `keyphrase_noun_chunk_pool` is passed (never concat-reparse) |
| temporal_dynamics, insight_eligibility, voice_contours, llm_speaker_summary, contextual_emotion, fine_grained_emotion, llm_custom_qa | Data outputs only (no group chart registry entry); **llm_speaker_summary** may also feed [group LLM synthesis](group_llm_synthesis_contract.md) |
| summary, llm_summary, narrative_summary, transcript_output | Blob-only composite; **llm_summary** may also feed [group LLM synthesis](group_llm_synthesis_contract.md) |
| llm_action_items, insights, semantic_similarity*, voice_mismatch/tension/fingerprint | Rows (+ charts where registered) |
| prosody (from voice_features / voice_charts_core / prosody_dashboard) | Registry-backed via existing `prosody` agg |

\* `semantic_similarity`, `semantic_similarity_advanced`, and `semantic_similarity` share one aggregation entry. **B14:** v2 motif envelope + group centroid match within a comparable provenance cohort (valid-zero sessions included; TF-IDF incomparable). `repetition_rows` remain `content_rows`; additive `motif_rows` + versioned `semantic_similarity_pooled`. Chart class: composite session bars + motif prevalence ([`group_charts_semantic_motifs_contract.md`](group_charts_semantic_motifs_contract.md)).

## keyphrases group aggregation (B16)

- Pool **per-transcript** noun_chunk ranks by `canonical_key` (never reparse concatenated multi-session text).
- Aggregate: sum `occurrence_count`, sum member `rank_weight` then re-normalise, `member_session_support`, display = mode.
- Drop phrases below `min_member_sessions` (default 2).
- Registry chart: `keyphrases.phrases.global` (top-N pooled rank_weight); requires `keyphrases_pooled` on chart_outcome allowlist.
- YAKE/KeyBERT: explicitly **deferred** for group pooling this wave.
- Wordclouds special-path: pooled noun_chunk cloud from explicit `keyphrase_noun_chunk_pool` into `run_group_wordclouds` (see [`pooled_variants.py`](../src/transcriptx/core/analysis/wordclouds/pooled_variants.py)).
- Runtime note: [`../runtime/keyphrases.md`](../runtime/keyphrases.md).
- Pooled chart contract: [`group_charts_keyphrases_pooled_contract.md`](group_charts_keyphrases_pooled_contract.md).

## transcript_quality group aggregation

ASR confidence is **not** comparable across ASR engines/models/normalisation policies.

- Members are grouped by `provenance.comparable_key`.
- The primary cohort is the largest compatible set; other members are counted as `incompatible_member_count` and excluded from pooled confidence metrics.
- Within a cohort (word-weighted, never unweighted mean of session summaries):
  - `coverage = sum(scored) / sum(eligible)`
  - `mean_score = sum(mean_i * scored_i) / sum(scored_i)`
  - `low_score_ratio = sum(low_score_words) / sum(scored)`
- Group charts emit session bars **only for the primary cohort**; they never blend incompatible provenance.

See also [runtime/transcript_quality.md](../runtime/transcript_quality.md).

## Insights / Overview UI (group subjects)

Pipeline already runs selected modules on each member. The web Insights and Overview blocks load **both**:

1. Group rollups (`*_rows.json`, summary blobs, optional [group LLM synthesis](group_llm_synthesis_contract.md))
2. Per-session member contracts via a session picker (`storage_root`-aware loader)

See [`docs/dev/web_blocks.md`](../dev/web_blocks.md) and [`docs/dev/group_functionality_audit_2026-07-17.md`](../archive/assessments/group_functionality_audit_2026-07-17.md) (E6/E7).

## Related docs

- [Group charts: default overview vs gallery](group_charts_default_overview.md) — session, temporal overlay, cross-session speaker, pooled single view
- [Phase 4 outcome table](../archive/assessments/group_charts_phase4_outcome_table.md) — per-`agg_id` chart decisions
- [Keyphrases pooled contract](group_charts_keyphrases_pooled_contract.md) — B16 noun_chunk group chart
- [Relational pooling model](group_charts_relational_pooling_model.md) — pooled semantics for interactions / contagion
- [Runtime keyphrases](../runtime/keyphrases.md) — single-transcript + install extras
