Type: CONTRACT
Authority: self

# Contract: group aggregate stats cross-session speaker (gallery)

**Stable viz_id pattern:** `group.stats.cross_session_speaker.speaker_{canonical_speaker_id}`

**Gallery-only:** These charts are **not** listed in `DEFAULT_GROUP_OVERVIEW_VIZ_IDS`. Opt-in for the default strip uses `CROSS_SESSION_SPEAKER_OVERVIEW_ALLOWLIST` in `chart_registry.py` (see [`group_charts_default_overview.md`](group_charts_default_overview.md)).

## 1. Metric (v1)

- **Only `word_count`** — per speaker per session, from the stats module `speaker_stats` list.
- Tuple layout matches `aggregate_stats_group`: each row is  
  `(duration, name, word_count, segment_count, tic_rate, _)`  
  where **`word_count`** is the **third** element (index 2), non-negative integer count for that display speaker in that transcript run.
- No other metrics in v1 (no segment_count, duration, or tic_rate cross-session charts in this family).

## 2. Source inputs

| Input | Location | Meaning |
| --- | --- | --- |
| Per-member stats payload | `PerTranscriptResult.module_results["stats"]` → `_extract_stats_payload` | Must include `speaker_stats` as a list of tuples as above. |
| `CanonicalSpeakerMap` | `GroupChartContext.canonical_speaker_map` | **Required** — same identity rules as sentiment cross-session. |
| Session order | `sort_per_transcript_results_for_overlay` | Consistent with other group overlay helpers. |

## 3. Identity and eligibility

- **`canonical_speaker_map` required** — no charts without it.
- Map display speaker `name` from each tuple to canonical id via `_build_display_to_canonical` and `_fallback_canonical_id` (same as sentiment cross-session).
- Emit **one bar chart per canonical speaker** only when:
  - **≥2 sessions** contribute a numeric `word_count` for that speaker, and
  - **≥2 non-null** values: `word_count` must be `int` or `float`, not `bool`.
- Skip sessions with missing stats module or empty / invalid `speaker_stats`.

## 4. Chart semantics

- **X:** session labels (`S{n} stem`, same style as sentiment cross-session).
- **Y:** `word_count` for that speaker in that session (raw counts, not normalized across group).

## 5. What this chart does not mean

- Not speaking rate, duration, or segment count (v1 is **word count only**).
- Not comparable wall-clock time across sessions (categorical sessions on the x-axis).

---

## 6. Metric (v2) — **segment count across sessions**

**Stable `viz_id` pattern:** `group.stats.cross_session_speaker.segment_count.speaker_{canonical_speaker_id}`

**Naming:** Contract text and chart titles use **“segment count across sessions”** so this family is never confused with **word count** cross-session charts (v1).

- **`segment_count` only** — fourth element (**index 3**) of each `speaker_stats` tuple  
  `(duration, name, word_count, segment_count, tic_rate, _)`.
- **Eligibility** matches v1: `canonical_speaker_map` required, ≥2 sessions with numeric values, ≥2 non-bool numeric `segment_count` points per canonical speaker, same identity rules as v1.
- **Gallery-only:** not in `DEFAULT_GROUP_OVERVIEW_VIZ_IDS` unless listed in `CROSS_SESSION_SPEAKER_OVERVIEW_ALLOWLIST`.
- **Chart semantics:** X = session labels (`S{n} stem`); Y = raw segment count for that speaker in that session.

### What v2 does not mean

- Not word count (see v1).
- Not duration or tic_rate.
- Not wall-clock alignment across sessions.
