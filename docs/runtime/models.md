Type: GUIDE
Authority: runtime/STORAGE.md

# Analysis models

Operational guide for choosing NLP/ML models used during analysis. This does not change storage or output contracts.

For Docker-specific wiring, see [docker.md](docker.md). For local LLM modules (`llm_summary`, `llm_speaker_summary`, `llm_action_items`, `narrative_summary`), see [llm.md](llm.md). For lexical diversity metrics (`lexical_diversity`), see [lexical_diversity.md](lexical_diversity.md). For emotion-family chart viz IDs and gallery captions (`emotion`, `contextual_emotion`, `fine_grained_emotion`), see [emotion_family_contracts_2026-07-18.md](../dev/emotion_family_contracts_2026-07-18.md#charts-gallery). For transcription (upstream of analysis), see [transcription.md](transcription.md).

## Quick presets

### Default (balanced speed / quality)

Shipped defaults target CPU-friendly English analysis:

| Area | Default |
|------|---------|
| spaCy (NER, highlights, …) | `en_core_web_md` |
| Semantic similarity + echoes | `sentence-transformers/all-MiniLM-L6-v2` |
| Semantic similarity v2 | `sentence-transformers/all-MiniLM-L6-v2` |
| BERTopic embeddings | `all-MiniLM-L6-v2` |
| Sentiment | `vader` (lexicon) |
| Emotion (lexical `emotion`) | NRCLex vocabulary association (`emotion_lexical` extra) |
| Contextual emotion (experimental) | Built-in profile `contextual_hartmann_distilroberta_v1` (`j-hartmann/emotion-english-distilroberta-base`, pinned Hub SHA `0e1cd914e3d46199ed785853e12b57304e04178b`, Apache-2.0) |
| Fine-grained emotion (experimental) | Built-in profile `fine_grained_samlowe_go_emotions_v1` (`SamLowe/roberta-base-go_emotions`, pinned Hub SHA `d75048347613a25d77de8cf6412eaae9fa7b26be`, MIT) |
| Dialogue acts | rule/heuristic classification (transformer disabled; TF-IDF/RF untrained scaffolding only) |
| Topic modeling (LDA/NMF) | sklearn bag-of-words (no neural embedding) |

The Docker image pre-installs `en_core_web_sm`, `en_core_web_md`, and `en_core_web_lg` (the latter matches the higher-accuracy preset below). Other spaCy models download on first use when downloads are enabled.

### Higher-accuracy English (slower)

Set in your **gitignored** `.env` (recommended) or project `config.json`:

```bash
TRANSCRIPTX_SPACY_MODEL=en_core_web_lg
TRANSCRIPTX_SEMANTIC_MODEL=sentence-transformers/all-mpnet-base-v2
TRANSCRIPTX_SEMANTIC_V2_MODEL=sentence-transformers/all-mpnet-base-v2
TRANSCRIPTX_EMOTION_MODEL=j-hartmann/emotion-english-distilroberta-base
TRANSCRIPTX_SENTIMENT_BACKEND=transformers
TRANSCRIPTX_BERTOPIC_EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
```

Then restart Compose so the container receives the variables (`docker compose up` reads `.env` for substitution and passthrough).

**Notes:**

- `en_core_web_lg` is pre-installed in the Docker image. Larger models such as `en_core_web_trf` still download on first use when downloads are enabled.
- `all-mpnet-base-v2` is much slower than MiniLM but usually better for semantic similarity and BERTopic.
- `sentiment_backend=transformers` uses `analysis.sentiment_model_name` (default `cardiffnlp/twitter-roberta-base-sentiment-latest`).
- For maximum English NER quality (slowest): `TRANSCRIPTX_SPACY_MODEL=en_core_web_trf` (transformer pipeline; large download).

## Docker: env without changing `.env.example`

`docker-compose.yml` passes optional model variables from the host into the container. Put **your** values in `.env` at the repo root (gitignored). `.env.example` stays a template with empty placeholders.

Compose does **not** inject every `TRANSCRIPTX_*` variable automatically—only those listed under `services.transcriptx-web.environment`. Model-related keys are passthrough entries; unset keys leave app defaults unchanged.

## Environment variables (model-related)

| Variable | Config target | Purpose |
|----------|---------------|---------|
| `TRANSCRIPTX_SPACY_MODEL` | spaCy runtime (`get_nlp_model`) | NER, highlights, insight eligibility, shared tokenization |
| `TRANSCRIPTX_SEMANTIC_MODEL` | `analysis.semantic_model_name` | Legacy semantic similarity, echoes paraphrase embeddings |
| `TRANSCRIPTX_SEMANTIC_V2_MODEL` | `analysis.semantic_similarity_v2.model_name` | `semantic_similarity_v2` module |
| `TRANSCRIPTX_EMOTION_MODEL` | legacy alias toward contextual profile (prefer `analysis.contextual_emotion.profile_id`) | Deprecated flat key; conflicting new+old values fail validation when both set |
| `TRANSCRIPTX_SENTIMENT_BACKEND` | `analysis.sentiment_backend` | `vader`, `transformers`, or `textblob` |
| `TRANSCRIPTX_BERTOPIC_EMBEDDING_MODEL` | `analysis.bertopic.embedding_model` | BERTopic only |
| `TRANSCRIPTX_ACTS_MODEL` | `analysis.acts.ml_model_name` | **No effect today** — acts use heuristics; transformer classifier is disabled |
| `TRANSCRIPTX_DISABLE_DOWNLOADS` | — | `1` blocks HF emotion/sentiment downloads (spaCy uses `TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD`) |
| `TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD` | — | `1` blocks spaCy auto-download (install models manually) |

LLM variables (`TRANSCRIPTX_LLM_*`) are documented in [llm.md](llm.md).

## Config file / UI alternatives

Nested settings can also live in project config (`CONFIG_DIR/config.json`, typically under your data dir) or Streamlit **Settings** for keys exposed in the GUI (`analysis.semantic_model_name`, `analysis.emotion_model_name`, `analysis.semantic_similarity_v2.model_name`, etc.).

Environment variables override file settings when both are set.

Example `config.json` fragment for sentiment + BERTopic without env vars:

```json
{
  "analysis": {
    "sentiment_backend": "transformers",
    "sentiment_model_name": "cardiffnlp/twitter-roberta-base-sentiment-latest",
    "bertopic": {
      "embedding_model": "sentence-transformers/all-mpnet-base-v2"
    },
    "semantic_similarity_v2": {
      "model_name": "sentence-transformers/all-mpnet-base-v2"
    }
  }
}
```

## Module-by-module reference

### Where larger models help

| Module | Config / env | Upgrade ideas |
|--------|----------------|---------------|
| **NER** | `TRANSCRIPTX_SPACY_MODEL` | `en_core_web_lg`, `en_core_web_trf` |
| **Semantic similarity** (legacy + v2) | `TRANSCRIPTX_SEMANTIC_MODEL`, `TRANSCRIPTX_SEMANTIC_V2_MODEL` | `all-mpnet-base-v2`, other sentence-transformers checkpoints |
| **Echoes** (semantic paraphrase) | `TRANSCRIPTX_SEMANTIC_MODEL` | Same as semantic model |
| **BERTopic** | `TRANSCRIPTX_BERTOPIC_EMBEDDING_MODEL` | Same embedding family as semantic |
| **Emotion** | `TRANSCRIPTX_EMOTION_MODEL` | Larger HF `text-classification` emotion models (English-tuned) |
| **Sentiment** | `TRANSCRIPTX_SENTIMENT_BACKEND=transformers` + `sentiment_model_name` | RoBERTa default; larger HF sentiment models |
| **LLM summary / narrative** | `TRANSCRIPTX_LLM_MODEL` | Larger Ollama model (8B+, etc.) |
| **Voice deep ER** | `analysis.voice.deep_mode` (default **on**), `deep_model_name` | Larger SUPERB / wav2vec ER checkpoints |
| **Transcription** (external) | WhisperX `WHISPERX_MODEL` | `large-v2`, `large-v3` — see [recipes/whisperx](../recipes/whisperx/README.md) |

### Where larger models do **not** apply

| Module | Why |
|--------|-----|
| **Topic modeling (LDA/NMF)** | sklearn `CountVectorizer` / `TfidfVectorizer`; no embedding model knob |
| **Dialogue acts (`acts`)** | Heuristic/rule classification only; transformer path disabled; `TRANSCRIPTX_ACTS_MODEL` does not enable BERT inference |
| **Wordclouds, deterministic summary, insights** | Heuristics / TF-IDF / templates |
| **Geocoding (NER maps)** | Nominatim lookup, not ML |

### Profiles vs models

`quick` / `full` analysis mode and `semantic_similarity_v2` profiles (`fast_v2`, `balanced_v2`, `deep_v2`) change **thresholds, timeouts, and candidate limits**—not the embedding model. Pick the model explicitly via env or config.

`ner_use_light_model` in quick mode only switches spaCy to `en_core_web_sm` when `TRANSCRIPTX_SPACY_MODEL` is unset (downgrade, not upgrade).

## Non-English transcripts (future)

Defaults are **English**. For other languages, language-matched models usually beat larger English checkpoints:

- spaCy: e.g. `fr_core_news_md` via `TRANSCRIPTX_SPACY_MODEL` (manual download; not in the default image)
- Embeddings: multilingual sentence-transformers (e.g. `paraphrase-multilingual-mpnet-base-v2`)
- Whisper: set `language` at transcription time

TranscriptX does not auto-select models from transcript `language` metadata today.

## Troubleshooting

- **First run slow after upgrade** — models download into `HF_HOME` / spaCy data dirs; cache under `./data` when using Compose.
- **spaCy `OSError` model not found** — run `python -m spacy download <model>` in the container or allow auto-download.
- **Out of memory** — `en_core_web_trf`, large sentence-transformers, and transformer sentiment/emotion need more RAM; stay on `md` + MiniLM if constrained.
- **Strict env** — `TRANSCRIPTX_CONFIG_STRICT=1` rejects unknown `TRANSCRIPTX_*` keys; use only documented names.
