# Contract: group aggregate prosody temporal overlay (Tier 2)

Authority for the cross-session line chart emitted by `ProsodyGroupChartGenerator` when `per_transcript_results` are available. Reads only the v1 segment artifact; see [`group_charts_prosody_segment_artifact_v1.md`](group_charts_prosody_segment_artifact_v1.md).

**Stable viz_id:** `group.prosody.temporal_overlay.global`

## 1. Source inputs

| Input | Location | Meaning |
| --- | --- | --- |
| Member artifact | `{member_output_dir}/prosody_dashboard/data/global/{base_name}_prosody_overlay_segments.v1.json` | Payload per segment artifact v1 doc. |
| `base_name` | `get_canonical_base_name(member.transcript_path)` | Matches `OutputService` naming. |

## 2. Y-axis (single fixed field)

For each segment object `seg`:

- Require `schema_version == 1` and `y_field == "rms_db"` at file root (if missing or mismatch, treat file as **unreadable** for this viz_id and skip the session).
- **y = seg["rms_db"]** when numeric (int/float, not bool). Otherwise skip that segment.
- **x (raw):** `seg["start"]` seconds.

## 3. Missing y-value behavior

- **Per segment:** Skip if `rms_db` missing or non-numeric.
- **Per session:** Keep the series only if **≥2** points remain after skips; else omit that session.
- **Global:** If no session qualifies, emit no chart for this viz_id.

## 4. X-axis normalization

- **Per session:** `t0` = minimum segment `start` (seconds) in that member file. Each point **x = (start − t0) / 60** (session-relative minutes).
- **Across sessions:** No wall-clock alignment (same as other group temporal overlays).

## 5. Series selection

At most **8** sessions: `cap_per_transcript_results_for_overlay` / shared overlay helpers.

## 6. What the chart does not mean

- Not z-scored dashboard timeline values; artifact stores **raw** `rms_db`.
- Not one continuous timeline across transcripts.
- Not comparable absolute time across sessions.

**Title rule:** Titles must include the exact phrases **cross-session overlay** and **session-relative minutes**.
