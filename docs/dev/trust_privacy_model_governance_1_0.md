Type: PRODUCT
Authority: self

# Trust, privacy, and model governance (1.0)

**Status:** draft licence matrix scaffolded (**0.9.5**); gate evidence still open  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §13  
**Related:** [release_severity_triage_1_0.md](release_severity_triage_1_0.md), [dependency_audit.md](dependency_audit.md), [runtime/models.md](../runtime/models.md)

Mandatory gate before 1.0. Missing licence/privacy truth for shipped models is a release blocker; incomplete polish of notices may be a known limitation only where legal/privacy risk is absent.

## Checklist

- [x] Third-party model and dataset **licence inventory** (draft matrix below — **0.9.5**)
- [ ] Model download origins and **gated-model** requirements (confirm each row)
- [ ] Voice embedding and speaker-identity **privacy wording**
- [ ] Confirmation that **no telemetry or remote processing** occurs unless explicitly configured
- [x] Secrets and **absolute-path** audit (secrets_check + hygiene; live paths cleaned **0.9.5**)
- [x] Dependency **vulnerability** checks (release CI pip-audit / clean-env / image pip-check — ongoing); **licence** NOTICE polish still open
- [ ] **AI output labelling**
- [ ] Model, prompt, and analytical-semantics identity in artifacts where needed
- [ ] Explicit definition of what **“reproducible”** means for stochastic LLM output

## Known limitations + model/dependency matrix (draft)

Draft only — sourced from [runtime/models.md](../runtime/models.md) defaults and pinned HF profile `licence=` fields in `hf_text_classification/profiles.py`. Not legal advice; verify Hub cards before 1.0 NOTICE publication.

| Component | Licence | Download / gated? | Privacy notes | 1.0 posture |
|-----------|---------|-------------------|---------------|-------------|
| spaCy `en_core_web_md` (default) | spaCy model licence (see spaCy / model card) | Docker preinstalls sm/md/lg; others download when enabled | Local NLP; no remote call once installed | Draft — confirm |
| spaCy `en_core_web_lg` / `en_core_web_trf` (optional upgrades) | spaCy model licence | Download on first use when enabled | Same | Optional |
| `sentence-transformers/all-MiniLM-L6-v2` (semantic / echoes / BERTopic / KeyBERT default) | Apache-2.0 (typical Hub card; verify) | Hugging Face Hub download when enabled | Local embeddings | Draft — confirm |
| `sentence-transformers/all-mpnet-base-v2` (higher-accuracy option) | Apache-2.0 (typical Hub card; verify) | Hub download when enabled | Local embeddings | Optional |
| NRCLex vocabulary (`emotion` lexical) | See NRCLex / NRC emotion lexicon terms | Via `emotion_lexical` extra | Lexicon association; not a neural model | Draft — confirm |
| Contextual emotion profile `contextual_hartmann_distilroberta_v1` (`j-hartmann/emotion-english-distilroberta-base`, SHA `0e1cd914…`) | **Apache-2.0** (profile `licence=`) | Hub download; pinned revision; experimental | Local classifier; experimental channel | Draft — confirm |
| Fine-grained emotion profile `fine_grained_samlowe_go_emotions_v1` (`SamLowe/roberta-base-go_emotions`, SHA `d750483…`) | **MIT** (profile `licence=`) | Hub download; pinned revision; experimental | Local classifier; experimental channel | Draft — confirm |
| Sentiment VADER (default) | NLTK / VADER terms | Bundled NLTK data | Lexicon; local | Draft — confirm |
| Sentiment transformers option `cardiffnlp/twitter-roberta-base-sentiment-latest` | See Hub model card | Hub download when `sentiment_backend=transformers` | Local classifier | Optional |
| Dialogue acts (heuristic default) | N/A (rule/heuristic) | None | No model download | Ship as heuristic |
| Topic modeling LDA/NMF (sklearn) | sklearn / SciPy stack | None beyond install | Local | Ship |
| BERTopic stack | See BERTopic / UMAP / HDBSCAN deps | Embedding model as above | Local; heavy | Draft — confirm |
| Ollama LLM modules (optional) | Model-dependent (user-chosen Ollama models) | User pulls models into Ollama | Local when Ollama is local; label AI outputs | Optional — document |
| Voice / speaker-match embeddings (ECAPA / `[voice]`) | See SpeechBrain / model cards | Optional extras; may download | **Speaker-identity sensitive** — privacy wording required | Draft — must word |

### NOTICE skeleton (optional, unfinished)

When gate evidence is collected, publish a short third-party notice (user-facing) listing redistributed / downloaded model identities and licence identifiers from the matrix above. Do not invent licence conclusions beyond documented Hub/profile fields.

Known limitations draft lives here until a dedicated user-facing page exists; link from ROADMAP / release notes at RC.
