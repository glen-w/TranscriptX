# Contract: group aggregate sentiment cross-session speaker (gallery)

**Stable viz_id pattern:** `group.sentiment.cross_session_speaker.speaker_{canonical_speaker_id}`

**Gallery-only:** These charts are **not** listed in `DEFAULT_GROUP_OVERVIEW_VIZ_IDS`. Opt-in for the default strip is governed by `CROSS_SESSION_SPEAKER_OVERVIEW_ALLOWLIST` in `chart_registry.py` (see [`group_charts_default_overview.md`](group_charts_default_overview.md)).

## 1. Metric (v1)

- **Compound mean (and related session fields)** — per display speaker per session, aligned via `CanonicalSpeakerMap`, same identity and eligibility rules as implemented in `SentimentGroupChartGenerator` / `generate_group_sentiment_cross_session_speaker_charts`.
- See generator code and stats cross-session doc for shared map semantics: [`group_charts_stats_cross_session_contract.md`](group_charts_stats_cross_session_contract.md) (identity section).

## 2. Source inputs

| Input | Location | Meaning |
| --- | --- | --- |
| Group aggregation outcome | `session_rows` / `speaker_rows` | Session-level sentiment fields; cross-session charts require `per_transcript_results` + `canonical_speaker_map`. |
| `CanonicalSpeakerMap` | `GroupChartContext.canonical_speaker_map` | **Required** for this family. |

## 3. Chart semantics

- **X:** session labels (`S{n} stem`, consistent with other group cross-session charts).
- **Y:** field-specific sentiment metric for that speaker in that session (see session field list in `sentiment_charts.py`).

## 4. What this chart does not mean

- Not a single timeline across transcripts (categorical sessions on the x-axis).
- Not comparable wall-clock time across sessions.
