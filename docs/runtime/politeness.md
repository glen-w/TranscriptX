# Politeness markers (`politeness`)

Speakers & Interaction module (B7) for **politeness / lexical formality / directiveness**.

## What it is

- Deterministic English lexicon + phrase match (T0 / light).
- Categories: `gratitude`, `apology`, `request_softener`, `polite_disagreement`, `bare_directive`, `formal_marker`.
- Derived: `soft_request_ratio` = softeners / (softeners + bare_directives).

## What it is not

- Not `affect_tension.polite_tension_index` (affect mismatch).
- Not `conversation_type` structural “formality” (meeting-likeness).
- Not linguistic accommodation / coordination; not post-1.0 `politeness_strategies` (B4 sibling citeable method — see backlog §3.2).
- Not B12 interaction equity (floor/interruption power) — compose beside this module in UI later; do not recompute here.

## Language

English lexicon v1. Non-English → abstention (`usable=false`).

## Config

Owned subtree `analysis.politeness`:

- `min_tokens_for_rates` (default 20)
- `enabled_categories` (empty = all)

## Modal ownership

Request frames (`could you`, `would you`, …) live only in this lexicon. Bare epistemic modals (`maybe`, `might`, …) live only in `epistemic_markers`.

## Core / extras

Core-mode compatible (T0 lexicon, no research-method sidecar, no optional extras). Offline/air-gapped: packaged EN lexicon only.

## Related

- Design: [`docs/dev/wave2_lexicon_linguistics_2026-07-23.md`](../dev/wave2_lexicon_linguistics_2026-07-23.md)
- Group pooled contract: [`docs/groups/group_charts_politeness_pooled_contract.md`](../groups/group_charts_politeness_pooled_contract.md)
