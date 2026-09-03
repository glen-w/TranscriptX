# Contract: group aggregate sentiment temporal overlay (Tier 2)

Authority for the cross-session **compound sentiment** line chart emitted when `SentimentGroupChartGenerator` has `per_transcript_results`. One chart family: one line per session (no per-speaker split in v1).

**Stable viz_id:** `group.sentiment.temporal_overlay.global`

## 1. Source inputs

| Input | Location | Meaning |
| --- | --- | --- |
| Per-member sentiment enriched transcript | `{member_output_dir}/sentiment/data/global/{base_name}_with_sentiment.json` | Same layout as single-run sentiment: JSON list or `{"segments": [...]}`. Each segment has `start` (seconds) and `sentiment.compound` in [-1, 1]. |
| `base_name` | `get_base_name(member.transcript_path)` | Matches sentiment output naming. |

## 2. Normalization rule

- **Per session:** `t0` = minimum segment `start` (seconds) in that member’s loaded segments (0 if none). For each segment with a numeric compound, **x = (start − t0) / 60** (session-relative minutes). **y = segment compound** (raw per segment, not a rolling window).
- **Across sessions:** No wall-clock alignment. Session A at x=3 and session B at x=3 are not the same instant.
- **Series selection:** At most **8** sessions; ordering is `order_index` ascending, then stable transcript-path stem sort. No config or UI.

## 3. X-axis meaning

Minutes from the first segment timestamp in that member’s enriched sentiment file. Reconstructed within-session timeline for visualization only.

## 4. What the chart does not mean

- Not one continuous timeline across all transcripts.
- Not comparable absolute time across sessions.
- Not speaker-level attribution (v1 aggregates all segments in the session into one series).
- Not topic prevalence, entity salience, or causal claims across sessions.

**Title rule:** Titles must include the exact phrases **cross-session overlay** and **session-relative minutes**.
