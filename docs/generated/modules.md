# Module Catalog

*This catalog is auto-generated from the ModuleRegistry.*

## Available Modules

| Module | Description | Category | Dependencies | Determinism |
|--------|-------------|----------|--------------|-------------|
| acts | Dialogue Act Classification | medium | None | T0 |
| conversation_loops | Conversation Loop Detection | light | None | T0 |
| echoes | Quote/Echo/Paraphrase Detection | medium | None | T1 |
| highlights | Highlights and conflict moments (quote-forward) | light | None | T0 |
| interactions | Speaker Interaction Analysis | medium | None | T0 |
| moments | Ranked Moments Worth Revisiting | light | momentum | T0 |
| momentum | Stall/Flow Index Analysis | medium | pauses | T0 |
| pauses | Silence and Timing Analysis | light | None | T0 |
| qa_analysis | Question-Answer Pairing and Response Quality | medium | acts | T1 |
| semantic_similarity | Semantic Similarity Analysis | heavy | None | T1 |
| semantic_similarity_advanced | Advanced Semantic Similarity with Analysis Integration | heavy | None | T1 |
| sentiment | Sentiment Analysis | medium | None | T1 |
| simplified_transcript | Simplified transcript (tics, agreements, repetitions removed) | light | None | T0 |
| stats | Statistical Analysis | light | None | T0 |
| summary | Executive brief summary derived from highlights | light | highlights | T0 |
| temporal_dynamics | Temporal Dynamics Analysis | medium | None | T1 |
| tics | Verbal Tics Analysis | light | None | T0 |
| topic_modeling | Topic Modeling | heavy | None | T2 |
| transcript_output | Generate human readable transcripts | light | None | T0 |
| understandability | Understandability Analysis | medium | None | T0 |
| wordclouds | Word Cloud Generation | light | None | T1 |

## Category Definitions

- **light**: Fast, minimal computation (< 1 second per transcript)
- **medium**: Moderate computation, may use ML models (1-10 seconds)
- **heavy**: Intensive computation, large models (10+ seconds)

## Determinism Tiers

- **T0**: Fully deterministic - same input always produces same output
- **T1**: Mostly deterministic - minor variations possible (e.g., floating point)
- **T2**: Non-deterministic - output depends on model initialization or randomness
