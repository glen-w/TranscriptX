Type: GUIDE
Authority: ../ARCHITECTURE.md

# Module Catalog

*This catalog is generated from the ModuleRegistry.*

## Available Modules

| Module | Description | Category | Dependencies | Determinism |
|--------|-------------|----------|--------------|-------------|
| corrections | Semi-automatic transcription accuracy tuning | light | None | T0 |
| acts | Dialogue Act Classification | medium | None | T0 |
| conversation_loops | Conversation Loop Detection | light | None | T0 |
| contagion | Emotional Contagion Detection | heavy | emotion | T1 |
| emotion | Emotion Analysis | medium | None | T1 |
| entity_sentiment | Entity-based Sentiment Analysis | heavy | ner, sentiment | T1 |
| affect_tension | Emotion + Sentiment mismatch and tension indices | medium | emotion, sentiment | T1 |
| interactions | Speaker Interaction Analysis | medium | None | T0 |
| ner | Named Entity Recognition | medium | None | T1 |
| semantic_similarity | Semantic Similarity Analysis (Legacy) | heavy | None | T1 |
| semantic_similarity_advanced | Advanced Semantic Similarity with Analysis Integration (Legacy) | heavy | None | T1 |
| semantic_similarity_v2 | Semantic similarity v2 (batched embeddings, vectorized similarity) | heavy | None | T1 |
| sentiment | Sentiment Analysis | medium | None | T1 |
| stats | Statistical Analysis | light | None | T0 |
| topic_modeling | Topic Modeling | heavy | insight_eligibility | T2 |
| transcript_output | Generate human readable transcripts | light | None | T0 |
| simplified_transcript | Simplified transcript (tics, agreements, repetitions removed) | light | None | T0 |
| understandability | Understandability Analysis | medium | None | T0 |
| lexical_diversity | Lexical diversity metrics (TTR, MTLD, hapax rate) | light | None | T0 |
| wordclouds | Word Cloud Generation | light | insight_eligibility | T1 |
| tics | Verbal Tics Analysis | light | None | T0 |
| insight_eligibility | Shared content-vs-style insight eligibility pipeline | light | tics | T0 |
| temporal_dynamics | Temporal Dynamics Analysis | medium | None | T1 |
| qa_analysis | Question-Answer Pairing and Response Quality | medium | acts | T1 |
| pauses | Silence and Timing Analysis | light | None | T0 |
| echoes | Quote/Echo/Paraphrase Detection | medium | None | T1 |
| momentum | Stall/Flow Index Analysis | medium | pauses | T0 |
| moments | Ranked Moments Worth Revisiting | light | momentum | T0 |
| highlights | Highlights and conflict moments (quote-forward) | light | insight_eligibility | T0 |
| summary | Executive brief summary derived from highlights | light | highlights | T0 |
| narrative_summary | Grounded executive narrative from deterministic summary (LLM) (LLM) | medium | summary | T2 |
| llm_summary | Abstractive transcript summary via local LLM (LLM) | medium | None | T2 |
| llm_speaker_summary | Abstractive per-speaker summaries via local LLM (LLM) | medium | None | T2 |
| llm_action_items | Extract structured action items via local LLM (LLM) | medium | None | T2 |
| insights | Content-first insights layer separated from style markers | light | insight_eligibility, highlights, topic_modeling | T0 |
| voice_features | Voice feature extraction and caching | heavy | None | T0 |
| voice_mismatch | Tone–Text mismatch detection (sarcasm/discord moments) | medium | voice_features | T0 |
| voice_tension | Conversation tension curve from voice | medium | voice_features | T0 |
| voice_fingerprint | Per-speaker voice fingerprint baseline and drift | medium | voice_features | T0 |
| prosody_dashboard | Prosody dashboard charts from voice features | medium | voice_features | T0 |
| voice_charts_core | Voice charts core: pauses + rhythm indices | medium | voice_features | T0 |
| voice_contours | Voice contours (slow; needs audio decode + pitch tracking) | medium | voice_features | T0 |

## Category Definitions

- **light**: Fast, minimal computation (< 1 second per transcript)
- **medium**: Moderate computation, may use ML models (1-10 seconds)
- **heavy**: Intensive computation, large models (10+ seconds)

## Determinism Tiers

- **T0**: Fully deterministic - same input always produces same output
- **T1**: Mostly deterministic - minor variations possible (e.g., floating point)
- **T2**: Non-deterministic - output depends on model initialization or randomness

## Related guides

- Local LLM modules: [runtime/llm.md](../runtime/llm.md)
- Lexical diversity: [runtime/lexical_diversity.md](../runtime/lexical_diversity.md)
