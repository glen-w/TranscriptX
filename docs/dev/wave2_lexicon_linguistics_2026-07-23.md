# Wave 2 lexicon linguistics — B6 + B7

Companion to [`analysis_module_backlog_2026-07-17.md`](analysis_module_backlog_2026-07-17.md). Shared kit + two new module IDs; lexicon-only v1 (T0).

## Module IDs

| ID | Backlog | UI group | Job |
|----|---------|----------|-----|
| `epistemic_markers` | B6 | Language & Meaning | Hedge / certainty / epistemic marker density |
| `politeness` | B7 | Speakers & Interaction | Politeness / lexical formality / directiveness |

## Shared hit schema

Each hit:

```json
{
  "speaker": "Alice",
  "segment_index": 12,
  "start": 42,
  "end": 49,
  "surface": "I think",
  "category": "epistemic_hedge",
  "module": "epistemic_markers"
}
```

`start`/`end` are character offsets into the segment `text` (inclusive-exclusive). No lemma field in v1.

## Rate denominators

- Tokenizer: Unicode word-like tokens, casefold, same spirit as lexical_diversity (`[^\W\d_]+(?:['\u2019-][^\W\d_]+)*`, drop length &lt; 2).
- Per eligible speaker and global: `token_count`, raw `category_counts`, `hits_per_100_tokens` (null when `token_count` &lt; `min_tokens_for_rates`).
- Pinned in payload metadata as `algorithm_version` / `tokenizer_version`.

## Ownership boundaries

| Existing | Stays | B6/B7 |
|----------|-------|-------|
| `tics` + verbal_tics hedges/softeners | Filler counts | Seed only; new lexicon files |
| `discourse_stoplist` hedge_terms | Content mask | Not product metrics |
| `acts` uncertainty/emphasis/apology/gratitude | Dialogue-act label | Seed cues; density ≠ act |
| `affect_tension.polite_tension_index` | Affect mismatch | Unrelated |
| `conversation_type` formality | Structural meeting-likeness | Unrelated |
| B12 equity indices | Floor/interruption power | Compose in UI later; not recomputed in `politeness` |

## Modal disambiguation (v1)

- Request frames (`could you`, `would you`, `can you`, `would you mind`, …) → **`politeness` / `request_softener` only**.
- Bare epistemic modals (`maybe`, `might`, `perhaps`, `possibly`) → **`epistemic_markers` / `modal_uncertainty` only**.
- Same surface string must not appear in both EN lexicon files.

## Taxonomies (v1 freeze)

**B6:** `epistemic_hedge` | `approximator` | `modal_uncertainty` | `certainty_booster`

Derived: `hedge_share` = (epistemic_hedge + approximator + modal_uncertainty) / total_marker_hits; `booster_share` = certainty_booster / total_marker_hits (null when total = 0).

**B7:** `gratitude` | `apology` | `request_softener` | `polite_disagreement` | `bare_directive` | `formal_marker`

Derived: `soft_request_ratio` = request_softener / (request_softener + bare_directive) when denominator &gt; 0 else null.

## Language

English lexicon v1. Non-`en` → `usable=false`, empty hits, `language_status=unsupported` (abstention). Do not wait on full P1 routing.

## Group aggregation

Additive category counts → `*_pooled.by_category`. Session/speaker rows include counts + rates. Mean of rates across sessions is descriptive only (same caveat as lexical_diversity).

## Out of scope (v1)

Classifier extras, ConvoKit, multilingual lexicons, Gong-style scorecards, B13 graphs, shared P2 platform (in-module spans suffice).
