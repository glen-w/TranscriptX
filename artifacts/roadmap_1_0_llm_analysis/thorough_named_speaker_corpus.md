# Thorough analysis — named-speaker corpus (qwen2.5:7b)

**Status:** measured complete (2026-08-07)  
**Package:** 0.9.8.7 · git `3c13bff`  
**Environment:** native host + Ollama `localhost:11434`  
**Model:** `qwen2.5:7b` (~7.6B; closest available ~6B-class text model; project-recommended for JSON LLM tasks)  
**Mode:** `full` (Thorough-equivalent recommended module set)  
**Selection:** managed library transcripts with `speaker_map_status=complete` (all speakers named or ignored)

## Qualifying transcripts (2/4 managed)

| Transcript | Segments | Audio | Speakers | Map |
|---|---:|---:|---:|---|
| `260615_Ana_phd_presentation_QA` | 297 | ~28.0 min | 10 named / 0 ignored | complete |
| `260615_Ana_phd_supervision_meeting` | 450 | ~35.9 min | 3 named / 0 ignored | complete |

Excluded managed: `_deep_test_large_norm` (partial, 1 unidentified), `_deep_test_mini_probe` (none).

## Wall timings

| Run | Wall | Status | Notes |
|---|---:|---|---|
| presentation_QA initial | **71.4 min** (4282.9 s) | **partial** | 4 LLM modules timed out at 600s while Ollama held `qwen3-vl:8b` |
| presentation_QA LLM retry | **31.7 s** | **succeeded** | `llm_summary`, `llm_speaker_summary`, `llm_action_items`, `narrative_summary` only; free Ollama + qwen2.5:7b |
| presentation_QA effective success (est.) | **31.9 min** (1914.5 s) | succeeded (composite) | initial wall − timeout dead time (2400s) + retry |
| supervision_meeting | **10.1 min** (606.2 s) | **succeeded** | 42 modules, 0 errors |
| **Corpus sum (effective)** | **42.0 min** | — | both qualifying transcripts |

## Top modules — supervision (clean success)

| Module | Duration | Status |
|---|---:|---|
| ner | 46.9s | RUN |
| wordclouds | 30.2s | RUN |
| bertopic | 17.9s | RUN |
| semantic_similarity | 17.1s | RUN |
| topic_modeling | 16.0s | RUN |
| summary | 14.3s | RUN |
| topic_shift | 13.6s | RUN |
| sentiment | 13.2s | RUN |
| llm_action_items | 7.0s | RUN |
| llm_speaker_summary | 6.5s | RUN |
| contextual_emotion | 5.0s | RUN |
| echoes | 4.7s | RUN |

## Top modules — presentation_QA (initial partial)

| Module | Duration | Status |
|---|---:|---|
| llm_action_items | 600.0s | FAIL |
| narrative_summary | 600.0s | FAIL |
| llm_summary | 600.0s | FAIL |
| llm_speaker_summary | 600.0s | FAIL |
| topic_shift | 545.4s | RUN |
| ner | 69.2s | RUN |
| wordclouds | 28.3s | RUN |
| bertopic | 23.6s | RUN |
| topic_modeling | 21.0s | RUN |
| semantic_similarity | 20.0s | RUN |
| sentiment | 17.8s | RUN |
| contextual_emotion | 15.7s | RUN |

## LLM notes

- Contended Ollama (vision model loaded) → 600s module timeouts → `final_status=partial` with pipeline continuation (honest recovery).
- Free Ollama + `qwen2.5:7b` → LLM modules complete in seconds–low tens on these corpora.
- Supervision LLM logical wall: 16.5 s · calls=5 · tok/s=43.423774911525655

## Artifacts

- Scratch logs: `artifacts/roadmap_1_0_llm_analysis/`
- Runs: see `corpus_timings.json`
- Roadmap: `docs/dev/pre_release_roadmap_1_0.md` §12
- Envelopes: `docs/dev/performance_envelopes_1_0.md`
