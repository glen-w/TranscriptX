Type: PRODUCT
Authority: analysis_quality_audit.md

# Analysis quality audit scaffold (generated)

**Status:** machine scaffold from `MODULE_REGISTRY_ORDER` (**0.9.5**)  
**Do not hand-edit rows** — regenerate with `python3 scripts/release/regen_module_docs.py`.  
Human judgements (meaningfulness, recommendation, severity) live in empty columns below and in [analysis_quality_audit.md](analysis_quality_audit.md).

| Module id | Description | Category | Dependencies | Determinism | Recommendation | Severity | Notes |
|-----------|-------------|----------|--------------|-------------|----------------|----------|-------|
| `acts` | Dialogue Act Classification | medium | None | T0 | | | |
| `conversation_loops` | Conversation Loop Detection | light | None | T0 | | | |
| `contagion` | Emotional Contagion Detection | heavy | emotion | T1 | | | |
| `emotion` | Emotion-associated vocabulary (NRC lexicon) | medium | None | T1 | | | |
| `contextual_emotion` | Contextual emotion (broad classifier, experimental) | heavy | None | T2 | | | |
| `fine_grained_emotion` | Fine-grained multi-label emotion (experimental) | heavy | None | T2 | | | |
| `entity_sentiment` | Entity-based Sentiment Analysis | heavy | ner, sentiment | T1 | | | |
| `affect_tension` | Emotion + Sentiment mismatch and tension indices | medium | emotion, sentiment | T1 | | | |
| `interactions` | Speaker Interaction Analysis | medium | None | T0 | | | |
| `ner` | Named Entity Recognition | medium | None | T1 | | | |
| `semantic_similarity` | Semantic similarity (batched embeddings, vectorized similarity) | heavy | None | T1 | | | |
| `sentiment` | Sentiment Analysis | medium | None | T1 | | | |
| `epistemic_markers` | Hedging / certainty / epistemic markers | light | None | T0 | | | |
| `keyphrases` | Keyphrase ranking (noun chunks / YAKE / KeyBERT) | medium | insight_eligibility | T1 | | | |
| `stats` | Statistical Analysis | light | None | T0 | | | |
| `topic_modeling` | Topic Modeling | heavy | insight_eligibility | T2 | | | |
| `bertopic` | BERTopic topic modeling (optional [bertopic]/[full] stack — see docs/dev/bertopic_optional_module.md) | heavy | insight_eligibility | T2 | | | |
| `transcript_output` | Generate human readable transcripts | light | None | T0 | | | |
| `simplified_transcript` | Simplified transcript (tics, agreements, repetitions removed) | light | None | T0 | | | |
| `understandability` | Understandability Analysis | medium | None | T0 | | | |
| `lexical_diversity` | Lexical diversity metrics (TTR, MTLD, hapax rate) | light | None | T0 | | | |
| `wordclouds` | Word Cloud Generation | light | insight_eligibility | T1 | | | |
| `tics` | Verbal Tics Analysis | light | None | T0 | | | |
| `transcript_quality` | ASR Confidence | light | None | T0 | | | |
| `insight_eligibility` | Shared content-vs-style insight eligibility pipeline | light | tics | T0 | | | |
| `temporal_dynamics` | Temporal Dynamics Analysis | medium | None | T1 | | | |
| `qa_analysis` | Question-Answer Pairing and Response Quality | medium | acts | T1 | | | |
| `pauses` | Silence and Timing Analysis | light | None | T0 | | | |
| `echoes` | Quote/Echo/Paraphrase Detection | medium | None | T1 | | | |
| `politeness` | Politeness / formality / directiveness markers | light | None | T0 | | | |
| `momentum` | Stall/Flow Index Analysis | medium | pauses | T0 | | | |
| `topic_shift` | Topic-shift chapter segmentation | medium | None | T0 | | | |
| `moments` | Ranked Moments Worth Revisiting | light | momentum | T0 | | | |
| `highlights` | Highlights and conflict moments (quote-forward) | light | insight_eligibility | T0 | | | |
| `summary` | Executive brief summary derived from highlights | light | highlights | T0 | | | |
| `narrative_summary` | Grounded executive narrative from deterministic summary (LLM) | medium | summary | T2 | | | |
| `llm_summary` | Abstractive transcript summary via local LLM | medium | None | T2 | | | |
| `llm_speaker_summary` | Abstractive per-speaker summaries via local LLM | medium | None | T2 | | | |
| `llm_action_items` | Extract structured action items via local LLM | medium | None | T2 | | | |
| `llm_custom_qa` | Answer custom questions against the transcript via local LLM | medium | None | T2 | | | |
| `chart_descriptions` | Per-chart LLM narratives (finalize-phase; after all charts) | medium | None | T2 | | | |
| `insights` | Content-first insights layer separated from style markers | light | insight_eligibility, highlights, topic_modeling | T0 | | | |
| `voice_features` | Voice feature extraction and caching | heavy | None | T0 | | | |
| `voice_mismatch` | Tone–Text mismatch detection (sarcasm/discord moments) | medium | voice_features | T0 | | | |
| `voice_tension` | Conversation tension curve from voice | medium | voice_features | T0 | | | |
| `voice_fingerprint` | Per-speaker voice fingerprint baseline and drift | medium | voice_features | T0 | | | |
| `prosody_dashboard` | Prosody dashboard charts from voice features | medium | voice_features | T0 | | | |
| `voice_charts_core` | Voice charts core: pauses + rhythm indices | medium | voice_features | T0 | | | |
| `voice_contours` | Voice contours (slow; needs audio decode + pitch tracking) | medium | voice_features | T0 | | | |
