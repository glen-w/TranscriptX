Type: CONTRACT
Authority: self

# Interactions semantics and turn-taking equity

Companion to [`group_charts_interactions_pooled_contract.md`](group_charts_interactions_pooled_contract.md) and [`group_charts_relational_pooling_model.md`](group_charts_relational_pooling_model.md).

## Semantics version

| Version | Meaning |
|---------|---------|
| missing / `1` | Legacy inverted initiated/received polarity |
| `2` (current, `INTERACTIONS_SEMANTICS_VERSION`) | Corrected actor→target roles |

Persisted on the **containing interactions result** (`semantics_version`), not only inside `equity`. Existing on-disk runs with missing/`1` require **re-analysis** before directional pooling is valid.

### Directional pool gate

If any included interactions payload is missing or non-current `semantics_version`:

- **Block** pooling of directional role counts and dominance-derived group fields (`interactions_pooled` speakers, dominance-averaged `speaker_rows`).
- **Do not** block session rows or non-directional session fields (`total_interactions`, `unique_speakers`, nullable equity indices).
- Emit **one** structured warning `INTERACTIONS_SEMANTICS_VERSION_MISMATCH` listing offending transcripts.

## Role direction (v2)

Event fields: `speaker_a` = interrupted / prior addressee; `speaker_b` = interrupter / responder.

| Family | Types | Actor (initiates) | Target (receives) | Matrix edge |
|--------|-------|-------------------|-------------------|-------------|
| Interruption | `interruption_overlap`, `interruption_gap` | interrupter (`speaker_b`) | interrupted (`speaker_a`) | actor→target |
| Response | `response` | responder (`speaker_b`) | addressee (`speaker_a`) | actor→target |

Unknown types are skipped (not counted). Loose `startswith("interruption")` is not used.

### Frozen dominance formula

\[
\mathrm{dominance}(s)=\frac{(I_\mathrm{init}+R_\mathrm{init})-(I_\mathrm{recv}+R_\mathrm{recv})}{I_\mathrm{init}+R_\mathrm{init}+I_\mathrm{recv}+R_\mathrm{recv}}
\]

when denominator > 0; else `0`. Both interruption and response roles contribute. Responses are not excluded by the polarity fix.

## Eligible speakers and duration

Shared helper: `transcriptx.core.utils.segment_duration.compute_eligible_speaker_durations` (also used by `speaker_stats` for duration only).

| Case | Handling |
|------|----------|
| Ineligible / unknown speakers | Excluded from roster and duration sums |
| Missing / non-numeric timestamps | Segment skipped for duration |
| `end < start` | Invalid; skipped |
| Zero-duration segment | Contributes `0`; speaker may remain eligible |
| Zero-duration speaker | Eligible with duration `0` if present in grouping |
| Overlaps | Sum raw segment lengths (claimed speaking time; not exclusive occupancy) |

## Canonical equity object

Scalars always `float | null`. Maps always `dict`. Abstentions: `{metric, reason}`.

**Not persisted:** `interruption_balance_index` — derive `1 - interruption_asymmetry_index` in chart/UI only.

| Field | Rule |
|-------|------|
| `floor_share` | duration / total valid duration; include zero-duration eligible speakers as `0.0` when total > 0 |
| `floor_entropy` | \(H=-\sum p_i\log_2 p_i\) (0-share terms contribute 0); null when abstaining |
| `floor_equity_index` | \(H/\log_2(n)\), **n = all eligible speakers** (incl. zero duration). Equal → 1; monopolised among multiple → 0. Abstain if total valid duration ≤ 0 or n < 2 |
| `interruption_asymmetry` | per involved speaker \((I-R)/(I+R)\) |
| `interruption_asymmetry_index` | mean absolute asymmetry over involved speakers; abstain if no interruptions (**inequity**: higher = more asymmetric) |
| `response_latency` | per responder: count, mean, median, p90 of **valid** `gap_before` |
| `response_latency_fairness_index` | clip\([0,1](1-\mathrm{CV})\) of per-responder mean latencies; abstain if <2 valid responders or overall mean of means is 0 |

### `gap_before` validity

Missing, non-finite, or negative → excluded (not coerced). Responder with no valid gaps is not a valid responder for fairness.

### Nearest-rank p90

Sort ascending; index \(\lceil 0.9 \times n \rceil - 1\) (0-based).

### Population CV

\(\sigma/\mu\) with population \(\sigma\) (divide by \(n\), not \(n-1\)).

### Abstention codes

`fewer_than_two_eligible_speakers`, `zero_total_duration`, `no_interruptions`, `fewer_than_two_valid_responders`, `zero_overall_mean_latency`.

Abstention → **null** on scalars and session-row equity fields — never `0`.

## Charts

- `interactions.equity.floor.global` — when **total valid duration > 0** (non-empty `floor_share`), even if floor equity index abstains.
- `interactions.equity.summary.global` — available indices independently; presentation balance = 1 − asymmetry; fixed 0–1 axis semantics in labels/notes.

## Group session fields

Nullable on session rows: `floor_equity_index`, `interruption_asymmetry_index`, `response_latency_fairness_index`.

**Not** in `interactions_pooled`: rates, shares, distributions, or equity indices (additive directional counts only, and only when semantics versions match).

## Equity contract scope

Equity and abstentions apply when an interactions analysis result is produced. Pipeline multi-speaker gates that skip the module entirely do not invent an interactions payload; UI must not promise equity cards for skipped modules.
