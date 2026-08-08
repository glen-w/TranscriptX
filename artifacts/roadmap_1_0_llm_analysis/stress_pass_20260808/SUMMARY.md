# Final Thorough stress pass — speaker-complete corpus (2026-08-08)

**Status:** passed  
**Package:** 0.9.8.8 · git `3b206e3`  
**Environment:** native host + Ollama localhost:11434  
**Model:** `qwen2.5:7b` (~7.6B)  
**Mode / preset:** `full` / `thorough` (42 suitable modules)  
**Selection:** managed transcripts with `speaker_map_status=complete`; groups whose every member is in that set  
**Started:** 2026-08-08T15:12:13+02:00 · **Finished:** 2026-08-08T16:20:52+02:00

## Qualifying set

| Transcript | Segments | Speakers | Map |
|---|---:|---:|---|
| `260615_Ana_phd_presentation_QA` | 297 | 10 named / 0 ignored | complete |
| `260615_Ana_phd_supervision_meeting` | 450 | 3 named / 0 ignored | complete |

| Group | Members |
|---|---|
| `_deep_test_bertopic_group2` | `260615_Ana_phd_supervision_meeting.json`, `260615_Ana_phd_presentation_QA.json` |
| `Perf smoke Ana multi-speaker` | `260615_Ana_phd_supervision_meeting.json`, `260615_Ana_phd_presentation_QA.json` |

Excluded managed: `_deep_test_*` / mini fixtures with incomplete or `none` maps; schema-broken `a_group_test`.

## Wall timings

| Run | Wall | Status | Modules | Notes |
|---|---:|---|---:|---|
| transcript `260615_Ana_phd_presentation_QA` | **9.8 min** (585.5 s) | `completed` | 42 | DAG module sum ~199 s; `chart_descriptions` est ~6.4 min |
| transcript `260615_Ana_phd_supervision_meeting` | **10.9 min** (651.9 s) | `completed` | 42 | DAG module sum ~261 s; `chart_descriptions` est ~6.5 min |
| group `_deep_test_bertopic_group2` | **24.0 min** (1442.6 s) | `completed` | 42 | both members + aggregation + group charts |
| group `Perf smoke Ana multi-speaker` | **24.0 min** (1439.4 s) | `completed` | 42 | same member pair; independent group run |
| **Corpus sum** | **68.7 min** (4119.4 s) | `passed` | 4 runs | transcripts 20.6 + groups 48.0 |

## Top DAG modules (transcripts)

**Presentation QA:** bertopic 29.5 s · ner 26.9 s · wordclouds 23.7 s · topic_shift 19.9 s · topic_modeling 14.6 s  

**Supervision:** ner 43.3 s · wordclouds 30.4 s · bertopic 24.9 s · semantic_similarity 17.1 s · llm_speaker_summary 15.9 s

## LLM notes

- Ollama held `qwen2.5:7b` only (no vision-model contention).
- Presentation QA: 4/4 LLM calls, logical wall 15.3 s.
- Supervision: 5/5 LLM calls, logical wall 44.1 s.
- All four runs: `success=true`, hard status `completed`/`succeeded`, 0 module failures.

## Artifacts

- `artifacts/roadmap_1_0_llm_analysis/stress_pass_20260808/batch_summary.json`
- `artifacts/roadmap_1_0_llm_analysis/stress_pass_20260808/corpus_timings.json`
- `artifacts/roadmap_1_0_llm_analysis/stress_pass_20260808/batch.log`
- Private mirror: `.local/release_evidence/20260808_thorough_stress_pass/`
- Run dirs: `…/260615_Ana_phd_presentation_QA/20260808_151213_94733139`, `…/260615_Ana_phd_supervision_meeting/20260808_152158_95318679`, group `…/7b9c6531-…/20260808_135224_e1985784`, `…/bba6641e-…/20260808_141623_8a279f84`
