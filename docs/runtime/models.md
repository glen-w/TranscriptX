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
| BERTopic embeddings | `all-MiniLM-L6-v2` (included in default install; `[bertopic]` is a compat alias) |
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
| `TRANSCRIPTX_BERTOPIC_EMBEDDING_MODEL` | `analysis.bertopic.embedding_model` | BERTopic embeddings only |
| `TRANSCRIPTX_BERTOPIC_MIN_TOPIC_SIZE` | `analysis.bertopic.min_topic_size` | Min docs per topic (default 5) |
| `TRANSCRIPTX_BERTOPIC_NR_TOPICS` | `analysis.bertopic.nr_topics` | `auto` or integer string |
| `TRANSCRIPTX_BERTOPIC_TOP_N_WORDS` | `analysis.bertopic.top_n_words` | Words per topic (default 10) |
| `TRANSCRIPTX_BERTOPIC_LABEL_WORDS` | `analysis.bertopic.label_words` | Words in display labels (default 3) |
| `TRANSCRIPTX_BERTOPIC_CALCULATE_PROBABILITIES` | `analysis.bertopic.calculate_probabilities` | Soft probs (default off) |
| `TRANSCRIPTX_BERTOPIC_TIMEOUT_SECONDS` | `analysis.bertopic.timeout_seconds` | Fit wall-clock budget (default 3600; continues pipeline on timeout) |
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
      "embedding_model": "sentence-transformers/all-mpnet-base-v2",
      "min_topic_size": 5,
      "nr_topics": "auto",
      "top_n_words": 10,
      "label_words": 3,
      "calculate_probabilities": false
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

**B14 cross-session motifs:** group matching requires a shared `provenance_compatibility_key` (backend, model/revision, embedding semantics version `semantic_v2_embed_sem.1`, pooling, truncation, L2, vector dim). TF-IDF fallback is **export-only / incomparable** (per-transcript vocabulary) and is never cross-matched.
| **Echoes** (semantic paraphrase) | `TRANSCRIPTX_SEMANTIC_MODEL` | Same as semantic model |
| **BERTopic** | `TRANSCRIPTX_BERTOPIC_*` (embedding + clustering knobs) | Same embedding family as semantic; packages in default install |
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

## Longitudinal voice matching (`[speaker_match]`)

Optional local speaker embeddings for suggested profile matches (see
`docs/contracts/speaker_profiles_voice_v1.md`). Default install does **not**
include this extra. Stage 8 lifecycle gate is **open**
(`FEATURE_GATE_COMPLETE = True`); production analyse/enrol/accept still require
privacy consent via `ActivationBarrier` (voice privacy defaults off).

Privacy consent **does not** enrol a reference corpus. Confirmed speaker links
alone are not voice evidence. Until you run Speakers detail → **Enrol trusted
voice from confirmed links** (writes under `speaker_profiles/voice/samples/`,
`embeddings/`, `vectors/`), analyse can succeed and still return no suggestion
(`NoReliableMatch`). That is expected with an empty corpus — not a SpeechBrain
failure. Enrol walks confirmed links up to the Settings → Storage
**Max confirmed links per voice enrol** cap
(`operator.voice_settings.json`, default 40).

| Field | Value |
|-------|--------|
| Extra | `speaker_match` (`speechbrain==1.0.2`, torch/torchaudio) |
| Model | `speechbrain/spkrec-ecapa-voxceleb` |
| Hub revision | `0f99f2d0ebe89ac095bcc5903c4dd8f72b367286` (pinned) |
| Embedding | 192-d float32 `<f4`, L2-normalised `.npy` |
| Offline | `TRANSCRIPTX_DISABLE_DOWNLOADS=1` → local files only; no model substitution |

Never silently swap embedding models; a change creates a new `model_generation_id`.

## Troubleshooting

- **First run slow after upgrade** — models download into `HF_HOME` / spaCy data dirs; cache under `./data` when using Compose.
- **spaCy `OSError` model not found** — run `python -m spacy download <model>` in the container or allow auto-download.
- **Out of memory** — `en_core_web_trf`, large sentence-transformers, and transformer sentiment/emotion need more RAM; stay on `md` + MiniLM if constrained.
- **Strict env** — `TRANSCRIPTX_CONFIG_STRICT=1` rejects unknown `TRANSCRIPTX_*` keys; use only documented names.
- **Voice match runs but finds no match** — confirm eligible embeddings exist under `speaker_profiles/voice/`; if only `active_generation.json` / `generations/` are present, enrol trusted voice from confirmed links first. Streamlit’s file watcher may probe SpeechBrain optional integrations (`k2`, `flair`); the web app collapses that into one WARNING and keeps full traces at DEBUG — unrelated to match quality.
