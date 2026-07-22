Type: CONTRACT
Authority: self

# Contract: group aggregate topic_shift temporal overlay (Tier 2)

Authority for the cross-session **topic-shift boundary** marker chart emitted by `TopicShiftGroupChartGenerator` when `per_transcript_results` are available. One line per session (session-level only). The same module also emits **session bar** charts from aggregated `session_rows` within one provenance cohort (separate family; see `GROUP_AGGREGATE_CHART_FAMILIES`).

**Stable viz_id:** `group.topic_shift.temporal_overlay.global`

## 1. Source inputs

| Input | Location | Meaning |
| --- | --- | --- |
| Per-member topic_shift events envelope | `{member_output_dir}/topic_shift/data/global/topic_shift.events.json` | Versioned envelope; unwrap via `load_topic_shift_events` (never bare `load_events_json`). |
| Group topic_shift stats | `outcome.session_rows` from dedicated aggregation | Used for Tier 1 session bars only; temporal overlay does not read aggregated scalars. |

## 2. Normalization rule

- **Per session:** Let `t0` be the minimum `time_start` among events in that member file (0 if none). For each event, **x = (time_start − t0) / 60** (session-relative minutes). **y** = `normalized_strength` from evidence when present, else event `severity`.
- **Across sessions:** No wall-clock alignment. Strength is **backend-local** and not cross-backend comparable.
- **Series selection:** At most **8** sessions via `cap_per_transcript_results_for_overlay`.

## 3. X-axis meaning

Minutes from the first plotted shift in that member’s events file. Reconstructed within-session timeline for visualization only.

## 4. What the chart does not mean

- Not one continuous timeline across all transcripts.
- Not comparable absolute time across sessions.
- Not cross-backend strength comparison (MiniLM vs TF-IDF must not be blended).

**Title rule:** Titles must include the exact phrases **cross-session overlay** and **session-relative minutes**.
