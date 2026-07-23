Type: RUNTIME
Authority: self

# Epistemic markers (`epistemic_markers`)

Language & Meaning module (B6) for **hedging / certainty / epistemic marker density**.

## What it is

- Deterministic English lexicon + phrase match (T0 / light).
- Per-segment marker **hits with character spans**, speaker/global counts and rates.
- Categories: `epistemic_hedge`, `approximator`, `modal_uncertainty`, `certainty_booster`.
- Derived: `hedge_share`, `booster_share`.

## What it is not

- Not `acts.uncertainty` (utterance dialogue-act label).
- Not `tics` filler/disfluency counts (though seed lists overlap historically).
- Not ASR confidence / `transcript_quality` word scores.

## Language

English lexicon v1. Non-English transcripts abstain (`usable=false`, `language_status=unsupported`).

## Config

Owned subtree `analysis.epistemic_markers`:

- `min_tokens_for_rates` (default 20)
- `enabled_categories` (empty = all categories)

## Outputs

- `{base}_epistemic_markers.json` / `.csv`
- Speaker category-rate charts
- Group: additive `epistemic_markers_pooled.by_category` + session bars

## Core / extras

Core-mode compatible (T0 lexicon, no optional extras, no model downloads). Offline/air-gapped: packaged EN lexicon only.

## Related

- Design: [`docs/dev/wave2_lexicon_linguistics_2026-07-23.md`](../dev/wave2_lexicon_linguistics_2026-07-23.md)
- Group pooled contract: [`docs/groups/group_charts_epistemic_markers_pooled_contract.md`](../groups/group_charts_epistemic_markers_pooled_contract.md)
