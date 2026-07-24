Type: PRODUCT
Authority: analysis_quality_audit.md

# Analysis quality audit judgements (0.9.7 draft)

**Status:** provisional agent draft for owner review — not final sign-off  
**Scaffold (machine rows):** [analysis_quality_audit_scaffold.md](analysis_quality_audit_scaffold.md)  
**Column authority:** [analysis_quality_audit.md](analysis_quality_audit.md)  
**Severity rules:** [release_severity_triage_1_0.md](release_severity_triage_1_0.md)

Judgements live here so `make docs-gen` can regenerate the scaffold without wiping human columns.

## Mandatory scrutiny

| Module id | Recommendation | Severity | Notes |
|-----------|----------------|----------|-------|
| `highlights` | retain | known limitation | Deterministic quote-forward; useful on English meetings. Relabel in UI as deterministic when LLM summary is also present. Multilingual quality varies. |
| `summary` | improve | must-fix | Deterministic executive brief derived from highlights. **Must not** read as AI-authored. Overview now badges it `Deterministic` vs `Local AI`. Keep below Local AI when both exist (existing precedence). |
| `llm_summary` | retain | must-fix (labelling) | Local AI abstractive summary. **Local AI** badge required on Insights/Overview (shipped 0.9.7). |
| `narrative_summary` | retain | must-fix (labelling) | LLM narrative grounded on deterministic summary. Same Local AI labelling. |
| `llm_action_items` | retain | must-fix (labelling) | Keep `HUMAN_REVIEW_BANNER` + Local AI badge. Do not present as ground truth. |
| `insights` | retain | post-1.0 | Content-first layer; prominence/tuning can continue post-1.0. |

## Full registry (provisional)

| Module id | Recommendation | Severity | Notes |
|-----------|----------------|----------|-------|
| `acts` | retain | known limitation | Heuristic dialogue acts; English-biased. |
| `conversation_loops` | retain | post-1.0 | Light T0; niche. |
| `contagion` | retain | known limitation | Depends on emotion; experimental-ish interpretation. |
| `emotion` | retain | known limitation | NRC lexicon association — not neural affect. |
| `contextual_emotion` | hide under Full / experimental | known limitation | Experimental classifier; keep off Guided defaults. |
| `fine_grained_emotion` | hide under Full / experimental | known limitation | Experimental; Full controls. |
| `entity_sentiment` | retain | known limitation | Needs NER+sentiment; sparse transcripts weak. |
| `affect_tension` | retain | post-1.0 | Derived indices. |
| `interactions` | retain | — | Core interaction analysis. |
| `ner` | retain | known limitation | spaCy model / language limits. |
| `semantic_similarity` | retain | — | Epoch-1 module id (ex-v2). |
| `sentiment` | retain | known limitation | VADER default; transformers optional. |
| `epistemic_markers` | retain | post-1.0 | Light T0. |
| `keyphrases` | retain | — | Shipped 0.8.x; YAKE/KeyBERT optional backends. |
| `stats` | retain | — | Baseline stats. |
| `topic_modeling` | retain | known limitation | Heavy; min-data sensitive. |
| `bertopic` | retain | known limitation | Stack is optional (`[bertopic]`/`[full]`/Docker) after leaving base so core/clean-env is not blocked by llvmlite; module still registered — see bertopic_optional_module.md. |
| `transcript_output` | retain | — | Human-readable export helper. |
| `simplified_transcript` | retain | post-1.0 | Convenience. |
| `understandability` | retain | known limitation | Heuristic readability. |
| `lexical_diversity` | retain | — | TTR/MTLD family. |
| `wordclouds` | retain | post-1.0 | Visual; not analytical truth. |
| `tics` | retain | — | Feeds insight eligibility. |
| `transcript_quality` | retain | known limitation | Needs ASR confidence when present. |
| `insight_eligibility` | retain | — | Shared pipeline; not user-primary. |
| `temporal_dynamics` | retain | post-1.0 | |
| `qa_analysis` | retain | known limitation | Depends on acts quality. |
| `pauses` | retain | — | Timing/silence. |
| `echoes` | retain | known limitation | Embedding-sensitive. |
| `politeness` | retain | known limitation | Marker heuristics; cultural limits. |
| `momentum` | retain | — | Stall/flow. |
| `topic_shift` | retain | — | Chapter segmentation. |
| `moments` | retain | post-1.0 | Ranked revisit moments. |
| `llm_speaker_summary` | retain | must-fix (labelling) | Local AI badge (0.9.7). |
| `llm_custom_qa` | retain | must-fix (labelling) | Optional Ollama; label AI. |
| `chart_descriptions` | retain | must-fix (labelling) | Finalize-phase LLM; label AI. |
| `voice_features` | retain | — | Prerequisite for voice stack; privacy-gated. |
| `voice_mismatch` | retain | known limitation | Needs voice + text. |
| `voice_tension` | retain | known limitation | |
| `voice_fingerprint` | retain | known limitation | Speaker-identity sensitive — privacy notice v2. |
| `prosody_dashboard` | retain | post-1.0 | |
| `voice_charts_core` | retain | post-1.0 | |
| `voice_contours` | retain | known limitation | Slow; audio decode. |

## Hardening backlog (severity-tagged)

| Finding | Severity | Action in 0.9.7 |
|---------|----------|-----------------|
| LLM surfaces without clear AI label | must-fix | Local AI badges on Insights/Overview LLM blocks |
| Deterministic summary looking like AI | must-fix | Overview badge `Deterministic` |
| Voice privacy copy missing | must-fix | `VOICE_PRIVACY_USER_NOTICE` + notice v2 |
| Experimental emotion modules in Guided defaults | known limitation | **Applied 0.9.8:** removed from Balanced heavy allowlist (`fine_grained_emotion` / `contextual_emotion` off Guided defaults); Thorough/Full still may include. No module delete. |
| Perf envelopes incomplete on large library | known limitation | Recipe ships; fill on human-testing hardware if needed |
| Chart LLM narratives unlabelled | must-fix | Local AI badge on Charts gallery LLM text (**0.9.7**) |
| Custom Q&A unlabelled | must-fix | Local AI badge on Insights custom QA block (**0.9.7**) |
| RTD hostname not live | known limitation | Flip checklist ready; owner slug gated |

## Owner sign-off

- [ ] Judgements reviewed
- [ ] Any `remove` / `deprecate` decisions confirmed (none proposed as hard delete in this draft)
- [ ] Severity backlog accepted for RC triage
