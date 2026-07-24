Type: PRODUCT
Authority: self

# Phase 4: group generic chart curation — outcome table

Forced decision per `agg_id`. Registry and field allowlists live in
[`registry.py`](../src/transcriptx/core/analysis/group_charts/registry.py)
(`build_group_chart_registry`, `GROUP_AGGREGATE_CHART_FAMILIES`); numeric field
subsets are in
[`generic_field_allowlists.py`](../src/transcriptx/core/analysis/group_charts/generic_field_allowlists.py).

| agg_id | Outcome | Session field allowlist (generic) | Notes |
| --- | --- | --- | --- |
| interactions | **composite** | `total_interactions`, `unique_speakers` (inner generic) | `InteractionsGroupChartGenerator`: session bars + **pooled** `interactions_pooled` additive counts ([relational model](group_charts_relational_pooling_model.md), [contract](group_charts_interactions_pooled_contract.md)). `speaker_rows` remain for CSV; charts use `interactions_pooled` only. |
| conversation_loops | keep generic | `total_loops`, `unique_speaker_pairs` | Pair-level dicts are not comparable across sessions. |
| qa_analysis | keep generic | statistics keys (7) | Flat, comparable session scalars. |
| echoes | keep generic | `total_events`, `counts_by_kind.{echo,paraphrase,explicit_quote}` | Fixed echo kinds only. |
| prosody | replace | n/a (prefix-filtered dedicated generator) | Never chart `raw` blob keys. Session bars from `prosody.*` / `voice_*` prefixes; temporal overlay `group.prosody.temporal_overlay.global` reads v1 segment artifact ([segment artifact](group_charts_prosody_segment_artifact_v1.md), [temporal contract](group_charts_prosody_temporal_contract.md)). |
| emotion | **replace** | n/a (`EmotionGroupChartGenerator`) | Session bars: exact keys under `global_emotions.{label}` for `CANONICAL_EMOTION_LABELS` only; temporal overlay: `group.emotion.temporal_overlay.global` (see contract doc). **Pooled:** `emotion_pooled` payload → `group.emotion.pooled.profile.global` ([contract](group_charts_emotion_pooled_contract.md)). |
| tics | **composite** | `total_tics` (inner generic) | `TicsGroupChartGenerator`: session bars via curated generic + **pooled** `group.tics.pooled.by_tic.global` ([contract](group_charts_tics_pooled_contract.md)). |
| ner | **pooled only** | n/a | `NerPooledGroupChartGenerator`; `ner_pooled` payload ([contract](group_charts_ner_pooled_contract.md)). |
| entity_sentiment | **pooled only** | n/a | `EntitySentimentPooledGroupChartGenerator` ([contract](group_charts_entity_sentiment_pooled_contract.md)). |
| topic_modeling | **pooled only** | n/a | `TopicModelingGroupChartGenerator`; `topic_modeling_pooled` ([contract](group_charts_topic_modeling_pooled_contract.md)). |
| bertopic | **pooled only** | n/a | `BertopicGroupChartGenerator`; `bertopic_pooled` ([contract](group_charts_bertopic_pooled_contract.md)). Optional `transcriptx[bertopic]` extra; group refit from pooled source segments. |
| understandability | keep generic | readability metric keys (8) | Matches `compute_understandability_metrics` output. |
| lexical_diversity | keep generic | `ttr`, `mtld`, `hapax_rate`, `token_count` | Descriptive per-session metrics; **do not** sum `type_count`. Ratio means are approximations, not pooled exact diversity. See [lexical_diversity.md](../runtime/lexical_diversity.md). |
| pauses | replace | n/a | `PausesGroupChartGenerator`: **session_summary_bars** from `session_rows` + **temporal_overlay** from `pauses.events.json`. |
| momentum | keep generic | momentum `stats` keys (5) | From `MomentumAnalysis` session stats dict. |
| affect_tension | keep generic | derived global indices (3) | `polite_tension_index`, `suppressed_conflict_score`, `institutional_tone_affect_delta`. |
| contagion | **pooled only** | n/a | `ContagionPooledGroupChartGenerator`; `contagion_pooled` edge merge ([relational model](group_charts_relational_pooling_model.md), [contract](group_charts_contagion_pooled_contract.md)). Session/speaker rows still written for CSV; no generic session charts. |
| keyphrases | **pooled only** | n/a | `KeyphrasesGroupChartGenerator`; `keyphrases_pooled` noun_chunks by `canonical_key` → `keyphrases.phrases.global` ([contract](group_charts_keyphrases_pooled_contract.md)). YAKE/KeyBERT + per-speaker group rows deferred. |
| stats | dedicated | n/a (`StatsGroupChartGenerator`) | Session/speaker summary bars; gallery **cross-session speaker**: word count `group.stats.cross_session_speaker.speaker_{id}`; **segment count across sessions** `group.stats.cross_session_speaker.segment_count.speaker_{id}` ([contract](group_charts_stats_cross_session_contract.md)). **Pooled totals:** `stats_pooled` → `group.stats.pooled.totals.global` ([contract](group_charts_stats_pooled_contract.md)); speaker **shares** deferred. |
| acts | dedicated | n/a (`ActsGroupChartGenerator`) | **Pooled audited:** `group.acts.global_acts_pie.global` (and bar when emitted) = corpus act mix ([contract](group_charts_acts_pooled_contract.md)). |
| sentiment | dedicated | n/a (`SentimentGroupChartGenerator`) | Includes gallery **cross-session speaker** compound-style charts ([contract](group_charts_sentiment_cross_session_contract.md)). |
| llm_action_items | keep generic | `item_count` | Session action-item counts; content rows in Data. |
| insights | keep generic | `theme_count`, `recurring_idea_count`, `notable_moment_count` | Session insight counts; content rows in Data. |
| semantic_similarity | composite (`SemanticSimilarityGroupChartGenerator`) | `total_repetitions`, `unique_patterns`, `motif_count`, `recurring_motif_count`, `drift_score` + motif prevalence | B14: centroid match within comparable cohort; TF-IDF incomparable; `repetition_rows` unchanged; see [`group_charts_semantic_motifs_contract.md`](group_charts_semantic_motifs_contract.md). |
| voice_mismatch | keep generic | `moments_count`, `mismatch_score_mean`, `mismatch_score_max` | Moment content rows in Data. |
| voice_tension | keep generic | `bins`, `tension_mean`, `tension_max` | Curve points as content rows; temporal overlay deferred. |
| voice_fingerprint | keep generic | `speakers`, `drift_moment_count` | Speaker baselines + drift content rows. |
| llm_summary | blob only | n/a | Collect per-member summaries; no charts. |
| narrative_summary | blob only | n/a | Collect per-member narratives; no charts. |
| llm_speaker_summary | data only | n/a | Speaker summary rows; no charts. |

**Temporal overlay viz_ids** (normalized pattern `group.{agg_id}.temporal_overlay.global`):

- `group.acts.temporal_overlay.global`
- `group.sentiment.temporal_overlay.global`
- `group.pauses.temporal_overlay.global`
- `group.emotion.temporal_overlay.global`
- `group.prosody.temporal_overlay.global`
