Type: GUIDE
Authority: self

# ASR confidence (`transcript_quality`)

Foundations module that surfaces **word-level ASR confidence** as reviewable evidence.

## What it is

- Model-produced **uncertainty evidence** from accepted word `score` fields (WhisperX imports today).
- Not estimated word error rate.
- Not proof that a word is incorrect.
- No synthetic overall “transcript quality” score.

User-facing label: **ASR Confidence**.

## Status semantics

| Status | Definition |
|--------|------------|
| `absent` | `scored_word_count == 0` |
| `partial` | `0 < scored_word_count < eligible_word_count` |
| `present` | every eligible word has a valid accepted score |

Counters distinguish missing scores, invalid scores, out-of-range scores, and unusable words (bad timing/text).

## Score policy

`accept_unit_interval_omit_otherwise`: finite numeric scores in `[0, 1]` are accepted; others are **omitted** (never clamped). Diagnostics record raw/accepted/invalid/out-of-range counts.

## Provenance

Each result records `import_adapter`, `asr_engine`, `model_identifier` (nullable), `source_score_field`, `normalisation_policy`, and a `comparable_key`.

Group pooling and group charts compare sessions **only within the same `comparable_key`**. Incompatible members are counted and excluded from pooled confidence metrics.

## Outputs

- Coverage, score distribution (histogram), percentiles
- Low-confidence **spans** and **clusters** with `playback` refs (`start`, `end`, `segment_index`)
- Insights block **ASR Confidence** with Open-in-transcript actions

## Config

Owned subtree `analysis.transcript_quality`:

- `low_score_threshold` (default 0.5)
- `max_gap_seconds` (0.75)
- `cluster_merge_seconds` (2.0)
- `max_spans` / `max_clusters`

## Out of scope (v1)

- Filler density / co-occurrence (deferred; use `tics` / `stats`)
- Invented confidence for non-WhisperX imports
- WER / reference alignment
