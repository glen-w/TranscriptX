# Contract: group aggregate pauses temporal overlay (Tier 2)

Authority for the cross-session **long pause** line chart emitted by `PausesGroupChartGenerator` when `per_transcript_results` are available. One line per session (session-level only; no per-speaker split in v1). The same module also emits **session summary bar** charts from aggregated `session_rows` (separate family; see `GROUP_AGGREGATE_CHART_FAMILIES`).

**Stable viz_id:** `group.pauses.temporal_overlay.global`

## 1. Source inputs

| Input | Location | Meaning |
| --- | --- | --- |
| Per-member pause events JSON | `{member_output_dir}/pauses/data/global/pauses.events.json` | Same artifact as single-run pauses: list of events with `kind`, `time_start`, `time_end` (seconds). |
| Group pause stats | `outcome.session_rows` from group aggregation | Used for Tier 1 session bar charts only; temporal overlay does not read aggregated scalars. |

Events included in the overlay: `kind` in `{long_pause, post_question_silence}` (same filter as the transcript-level long-pauses timeline chart).

## 2. Normalization rule

- **Per session:** Let `t0` be the minimum `time_start` among included events in that member file (0 if none). For each included event, **x = (time_start − t0) / 60** (session-relative minutes). **y = time_end − time_start** (gap duration in seconds).
- **Across sessions:** No wall-clock alignment. Session A at x=2 and session B at x=2 are not the same instant.
- **Series selection:** At most **8** sessions. Ordering: `order_index` ascending (from `PerTranscriptResult`), then stable transcript path stem sort. Same rule as group sentiment temporal overlay.

## 3. X-axis meaning

Minutes from the first **included** pause event’s start time in that member’s `pauses.events.json`. Reconstructed within-session timeline for visualization only.

## 4. What the chart does not mean

- Not one continuous timeline across all transcripts.
- Not comparable absolute time across sessions.
- Not speaker-level attribution (v1 uses session-global event streams only).
- Not total silence or gap structure beyond the included event kinds.

**Title rule:** Titles must include the exact phrases **cross-session overlay** and **session-relative minutes**.
