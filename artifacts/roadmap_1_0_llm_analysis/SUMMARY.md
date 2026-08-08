# Thorough full-preset LLM analysis (speaker-complete corpus)

Date: 2026-08-07  
Package: 0.9.8.7  
Model: `qwen2.5:7b` (shared)  
Mode: `full` (default module set)

## Eligibility

Only managed transcripts with `speaker_map_status=complete`:

- `260615_Ana_phd_presentation_QA.json` (297 segs, 10 speakers, ~28 min)
- `260615_Ana_phd_supervision_meeting.json` (450 segs, 3 speakers, ~36 min)

Excluded: `_deep_test_large_norm` (partial — 1 unidentified), fixtures (`none`).

Local-only fix applied before runs: `schema_version` `"1.0"` → `1` so loaders accept the files under the integer-1 epoch (gitignored data files).

## Timings

| Run | Wall | Status | Run dir |
|-----|-----:|--------|---------|
| Presentation QA (initial, contended Ollama) | 71.4 min | partial (4 LLM soft-timeouts) | `…/20260807_171909_15949872` |
| Presentation QA LLM retry (free Ollama) | 31.7 s | succeeded | `…/20260807_232957_38197390` |
| Presentation QA effective success (est.) | ~31.9 min | composite | initial − 2400 s timeout dead time + retry |
| Supervision (free Ollama) | 10.1 min | succeeded (42 modules) | `…/20260807_233852_38732557` |
| **Corpus effective sum** | **~42.0 min** | — | both qualifying transcripts |

See curated JSON: `corpus_timings.json`, `qa_timings.json`, `supervision_timings.json`.  
Roadmap home: `docs/dev/performance_envelopes_1_0.md` § Thorough full-preset LLM timings; programme pointer in `docs/dev/pre_release_roadmap_1_0.md` §12.
