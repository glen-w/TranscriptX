# Lexical diversity analysis

Deterministic module (`lexical_diversity`, tier **T0**, category **light**) that measures vocabulary variety per speaker and globally. It does **not** call an LLM and has **no** pydantic config — thresholds and bucket size are module constants.

Distinct from `understandability.lexical_density` (NLTK tokenizer / readability context). This module uses a pinned Unicode tokenizer and reports `ttr`, `mtld`, and `hapax_rate`.

## Requirements

Registry requirements: `SEGMENTS` + `SPEAKER_LABELS` only (`gate_on_turn_taking_speakers: true`).

Segment timestamps are **optional**. When valid finite non-negative `start`/`end` values are present on all eligible segments, global **time buckets** are emitted; otherwise `time_buckets` is `[]` and analysis still succeeds.

## Metrics

| Metric | Definition | Empty / short text |
|--------|------------|--------------------|
| `token_count` / `type_count` / `hapax_count` | Counts after tokenization | `0` when empty |
| `ttr` | `type_count / token_count` | `null` when empty |
| `hapax_rate` | `hapax_count / type_count` (types denominator) | `null` when empty |
| `mtld` | Forward + reverse MTLD (factor threshold `0.72`), averaged | `null` when tokens below `MIN_MTLD_TOKENS` (50) |

JSON never contains NaN or Infinity. Canonical JSON keeps full finite precision; CSV rounds display floats to 6 decimal places and writes empty cells for null MTLD/rates.

### Tokenizer (v1)

- Case-fold, then match `[^\W\d_]+(?:['\u2019-][^\W\d_]+)*`
- Tokens shorter than 2 characters are dropped
- Contractions/possessives/hyphenated forms stay one token (`don't`, `speaker's`, `state-of-the-art`)
- Digits alone and underscores as token characters are excluded (`hello_world` → `hello`, `world`)

Metadata in every payload includes `schema_id`, `algorithm_version`, `tokenizer_version`, `mtld_factor_threshold`, `min_mtld_tokens`, and `bucket_seconds` (60).

### Interpretation limits

- **TTR** is highly length-sensitive — do not treat higher TTR as unconditionally “better”.
- **MTLD** reduces length sensitivity but is unstable on short inputs (hence the 50-token floor).
- **Hapax rate** can reflect names, ASR errors, or topic-specific vocabulary.

## Output layout

```text
lexical_diversity/data/global/{base}_lexical_diversity.json
lexical_diversity/data/global/{base}_lexical_diversity.csv
lexical_diversity/charts/.../lexical-ttr.png   # and mtld / hapax-rate when data allows
```

JSON envelope (`schema_id`: `transcriptx.lexical_diversity.v1`):

- `metadata` — algorithm/tokenizer constants
- `global_stats` — metrics over **eligible** concatenated text (same population as speaker analysis)
- `speaker_stats` — per eligible turn-taking speaker
- `time_buckets` — global-only buckets (`[t0 + k*60, t0 + (k+1)*60)` by segment start); empty when timestamps unavailable
- `exclusions` — skipped segment counts / reasons

CSV is one tidy table with columns: `scope`, `speaker`, `bucket_start`, `bucket_end`, metric fields. Scopes: `global` \| `speaker` \| `time_bucket`.

## UI and export

- **Insights** (`default` layout): block `lexical_diversity_block` shows global metrics, per-speaker table, and optional time buckets.
- **Overview** module metrics: summary extractor shows global TTR/MTLD/hapax with a length-sensitivity caption.
- **Charts gallery**: viz IDs `lexical_diversity.ttr.speaker`, `.mtld.speaker`, `.hapax_rate.speaker` (MTLD omits null bars).
- **Zip export**: JSON, CSV, and chart PNGs are included via the manifest-driven export path.

## Group aggregation

Session/speaker rows are collected for group charts. Allowlisted numeric fields: `ttr`, `mtld`, `hapax_rate`, `token_count`.

- `token_count` is additive across transcripts.
- `type_count` is **not** summed (vocabulary overlap would invalidate derived TTR).
- Mean/median of ratio metrics across sessions are **descriptive approximations**, not exact pooled lexical diversity. No full token vocabularies are persisted for exact cross-session recomputation.

## Related docs

- LLM modules: [llm.md](llm.md)
- Group chart curation: [group_charts_phase4_outcome_table.md](../archive/assessments/group_charts_phase4_outcome_table.md)
- Web blocks: [web_blocks.md](../dev/web_blocks.md)
