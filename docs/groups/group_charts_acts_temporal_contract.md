Type: CONTRACT
Authority: self

# Contract: group aggregate acts temporal overlay (Tier 2)

This document is the authority for the **single** cross-session acts line chart emitted by `ActsGroupChartGenerator` when per-member run results are available. Other modules or chart families must not reuse this contract without their own document and review.

**Stable viz_id:** `group.acts.temporal_overlay.global`

## 1. Source inputs

| Input | Location | Meaning |
| --- | --- | --- |
| Per-member acts enriched transcript | `{member_output_dir}/acts/data/global/{base_name}_with_acts.json` | Same artifact as single-transcript acts: a JSON array of segments with `start` (seconds), `dialogue_act`, and speaker fields consumed by `extract_speaker_info` / `get_speaker_display_name`. |
| `base_name` | `get_base_name(member.transcript_path)` | Basename of the original transcript file, matching acts output layout. |
| Group act counts | `outcome.session_rows` / `speaker_rows` as reconstructed in `ActsGroupChartGenerator` | Used only to choose which act types appear on the y-axis (`acts_over_5` style filter vs global summed counts), consistent with single-run acts temporal charts. |

If a member file is missing or empty, that session contributes no series.

## 2. Normalization rule

- **Per session:** Let `t0` be the minimum segment `start` (seconds) in that member’s loaded segments (0 if none). For each plotted point, **x = (start − t0) / 60**, i.e. **minutes from the start of that session’s enriched timeline**.
- **Across sessions:** No alignment to wall-clock or calendar time. Session A at x=5 and session B at x=5 are **not** the same instant.
- **Member-run ordering / cap:** At most **8** member runs, ordered by `order_index` ascending then stable transcript path stem (shared helper `cap_per_transcript_results_for_overlay` in `overlay_series.py`). Each run still contributes one series per named speaker (same as before the cap).
- **Y values:** Integer index of the segment’s `dialogue_act` within the session’s eligible act-type list (same mapping as transcript-level acts temporal charts: only acts that pass the global frequency threshold).

## 3. X-axis meaning

The horizontal axis is **minutes elapsed since the first segment timestamp in that member run’s acts enriched file**. It is a **reconstructed within-session timeline** for visualization only.

## 4. What the chart does not mean

- It is **not** a single continuous timeline spanning all transcripts.
- It is **not** wall-clock comparable across sessions (offsets are per session).
- It does **not** imply topic prevalence, entity importance, or causal order **between** sessions.
- It does **not** recover silences or gaps beyond what segment `start` values encode.

Chart titles include wording that references **cross-session overlay** and **per-session time origin** so the UI stays aligned with this contract.
