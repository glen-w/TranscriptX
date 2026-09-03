# Theme A — Insights & analysis quality

Status: active (1.x)  
Last updated: 2026-08-10

**Roadmap home:** [docs/ROADMAP.md](../ROADMAP.md) §A  
**Product constraint:** Prefer deepen-in-place; label Deterministic vs Local AI honestly; do not keep weak deterministic fallbacks merely to claim non-AI coverage ([PRODUCT.md](../PRODUCT.md)).

## Goal

Stronger deterministic / hybrid insights: clearer, more useful non-LLM outputs with less noise; trustworthy empty/partial states; hybrid LLM paths inherit a cleaner deterministic base.

## Locked decisions

1. **Shared signal first** — raise quality in `phrase_quality` + `insight_eligibility` before inventing new insight detectors.
2. **Insights themes use `theme_label_policy`** — same bar as summary theme labels (stricter than `content_phrase_policy`).
3. **Abstain over pad** — if fewer than `min_themes_for_signal` themes pass the floor, emit empty themes + `status: insufficient_signal` rather than weak fillers.
4. **Schema v3** — each theme/idea row may carry `evidence_quote_ids`, `confidence`, `preference_tier`, and score breakdown; bump `schema_version` to 3.
5. **Topic soft boost only** — `topic_modeling` may boost an existing theme when labels overlap; it never invents themes. Dependency remains soft (missing topics = no boost).
6. **Overview focus honesty** — deterministic overview omits a focus clause when no high-tier theme labels survive; no fallback to emblematic filler phrases for focus text.
7. **Hybrid inherits base** — `narrative_summary` continues to rewrite only the deterministic summary findings; improving summary improves hybrid without prompt inventiveness.
8. **B18 LLM insight narratives** — deferred until provenance fields (P2-lite on schema v3 rows) are stable; Local AI only, never replacing deterministic theme lists.

## Signal rules

| Layer | Rule |
|-------|------|
| Phrase hard rejects | Empty, all-stopwords, discourse formulas, light-verb constructions, tic/discourse mask, pronoun shards, no content token, short shards |
| Eligibility floor | Default `min_score=0.18`; single-token candidates require `spread > 0` or `recurrence > 0` |
| Insights compose | Diversity via `select_diverse_themes`; caps from `analysis.insights` config |
| Confidence bands | `high` if total≥0.55 and (spread≥0.15 or recurrence≥0.2); `medium` if total≥0.35; else `low` (low rows may be dropped by floor) |

## Schema v3 sketch

```json
{
  "schema_version": 3,
  "status": "ok | insufficient_signal",
  "status_reason": null,
  "key_themes": [
    {
      "phrase": "budget risk",
      "score": {"total": 0.72, "spread": 0.3, "recurrence": 0.4},
      "confidence": "high",
      "preference_tier": 0,
      "evidence_quote_ids": ["q:..."],
      "topic_corroborated": false
    }
  ],
  "recurring_ideas": [],
  "style_markers": {},
  "notable_moments": [],
  "phrase_quality_version": 3
}
```

## Empty-state matrix (UI)

| Condition | User-facing copy |
|-----------|------------------|
| Insights module not run / failed | Existing quiet unavailable / module-required hint |
| `status == insufficient_signal` (content focus) | “Not enough clear content themes in this transcript.” |
| Eligibility / highlights missing for content block | “Content themes need Insight eligibility and Highlights in this run.” |
| Style markers empty | “No style indicators.” (unchanged) |
| Deterministic summary abstains on focus | Overview still shows speaker count / duration; no invented focus clause |

## Config knobs (`analysis.insights`)

| Field | Default | Role |
|-------|---------|------|
| `top_themes` | 8 | Cap for key themes |
| `top_recurring_ideas` | 8 | Cap for recurring ideas |
| `top_notable_moments` | 8 | Cap for notable moments |
| `min_theme_score` | 0.18 | Compose-time floor (aligned with eligibility) |
| `min_themes_for_signal` | 2 | Below this → abstain |
| `overview_theme_cap` | 5 | Suggested UI cap on Overview |
| `topic_boost` | 0.05 | Soft score boost when topic label overlaps |

Eligibility: `analysis.insight_eligibility.min_score` default `0.18`; `require_spread_or_recurrence_for_singletons` default `true`.

## Acceptance checklist

- [ ] Banned fillers never appear in `insights.key_themes` or `summary.key_themes` (unit + smoke)
- [ ] Abstention path covered when only weak phrases exist
- [ ] Evidence quote ids present when highlights themes attach
- [ ] Deterministic overview omits filler focus
- [ ] Commitments require content beyond light-verb stems
- [ ] Insights UI hides empty/abstention sections instead of sparse tables
- [ ] `PHRASE_QUALITY_VERSION` bumped when hard-reject semantics change
- [ ] Corpus before/after notes for 2–3 English meetings (manual)

## Out of scope (this theme wave)

- New module IDs
- Multilingual phrase-resource expansion (Theme M / known limitation)
- SQLite analytics (Theme J)
- Reintroducing Insights → Analysis tab
- Full B18 Local-AI insight narratives (follow-on after P2-lite)

## Corpus probe notes (deep-test 2026-08-10)

| Run | Transcript | Insights status | Notable themes |
|-----|------------|-----------------|----------------|
| mini Python | `data/transcripts/mini_transcript.json` | `ok` | google cloud support, new york stakeholders, market street |
| large Theme A modules | `_deep_test_large_norm.json` (1007 segs / 13 speakers) | `ok` after log-freq + greeting rejects (was `insufficient_signal` with linear freq + min_score 0.28) | kitchen fairy, cape town, south africa, social media |
| group | mini + large | member runs green; group finalize `partial` with manifest/run_results present | — |

Hardening during deep-test: log1p frequency scoring; greetings/`et cetera` discourse rejects; eligibility/insights floor `0.18`; emblematic-phrase fallback before abstention; `topic_modeling` optional so insights stays on quick/balanced.
