Type: CONTRACT
Authority: self

# Contract: group aggregate emotion temporal overlay (Tier 2)

Authority for the cross-session line chart emitted by `EmotionGroupChartGenerator` when `per_transcript_results` are available. Tier 1 session bar charts read aggregated `session_rows.global_emotions` (separate family).

**Stable viz_id:** `group.emotion.temporal_overlay.global`

## 1. Source inputs

| Input | Location | Meaning |
| --- | --- | --- |
| Per-member enriched transcript | `{member_output_dir}/emotion/data/global/{base}_with_emotion.json` | Segment list (same layout as single-run emotion output). |
| Group emotion session bars | `outcome.session_rows` / `global_emotions` | Used for Tier 1 only; overlay reads member files only. |

## 2. Y-axis (single fixed scalar)

For each segment, define **y** as follows (no alternate fields for this viz_id):

- Let `p = segment["context_emotion_primary"]`. Require `p` to be a non-empty string.
- Let `S = segment.get("context_emotion_scores")`. Require `S` to be a `dict`.
- **y = S[p]** only when `S[p]` is numeric (int/float, not bool). Otherwise this segment contributes **no point**.

There is **no** fallback to other keys in `S`, NRC-only blobs, or derived maxima.

## 3. Missing y-value behavior

- **Per segment:** If the scalar is undefined (missing primary, missing scores, missing key, or non-numeric), **skip that segment** (omit point).
- **Per session (series):** After skips, **keep** the series only if **at least two** points remain. If fewer than two, **omit that session’s series** from the overlay (do not fail other sessions).
- **Global:** If no session qualifies, emit no temporal chart for this viz_id.

## 4. X-axis normalization

- **Per session:** Let `t0` be the minimum segment `start` (seconds) among segments in that member file (0 if none). For each included point, **x = (start − t0) / 60** (session-relative minutes).
- **Across sessions:** No wall-clock alignment (same semantics as sentiment/acts/pauses overlays).

## 5. Series selection

At most **8** sessions. Ordering: `order_index` ascending, then stable transcript path stem sort (via `cap_per_transcript_results_for_overlay` / shared overlay helpers).

## 6. What the chart does not mean

- Not one continuous timeline across transcripts.
- Not comparable absolute time across sessions.
- Not a different emotion metric than `context_emotion_scores[context_emotion_primary]`.

**Title rule:** Titles must include the exact phrases **cross-session overlay** and **session-relative minutes**.
