Type: PRODUCT
Authority: self

# Trust, privacy, and model governance (1.0)

**Status:** gate closed for programme purposes (**0.9.7** drafts; Hub-card residual **dropped** 2026-08-07)  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §13  
**Related:** [release_severity_triage_1_0.md](release_severity_triage_1_0.md), [dependency_audit.md](dependency_audit.md), [runtime/models.md](../runtime/models.md), [NOTICE](../../NOTICE)

Mandatory gate before 1.0. Missing licence/privacy truth for shipped models is a release blocker; incomplete polish of notices may be a known limitation only where legal/privacy risk is absent.

## Checklist

- [x] Third-party model and dataset **licence inventory** (matrix below — **0.9.5**)
- [x] Model download origins and **gated-model** requirements (rows below)
- [x] Voice embedding and speaker-identity **privacy wording** (`VOICE_PRIVACY_USER_NOTICE`, notice **v2**, Settings Speakers panel — **0.9.7**)
- [x] Confirmation that **no telemetry or remote processing** occurs unless explicitly configured (see § Telemetry)
- [x] Secrets and **absolute-path** audit (secrets_check + hygiene; live paths cleaned **0.9.5**)
- [x] Dependency **vulnerability** checks (release CI pip-audit / clean-env / image pip-check — ongoing); **licence** NOTICE published (**0.9.7**)
- [x] **AI output labelling** (Local AI badges on Insights/Overview LLM surfaces — **0.9.7**)
- [x] Model, prompt, and analytical-semantics identity in artifacts where needed (provenance badges + existing artifact provenance fields)
- [x] Explicit definition of what **“reproducible”** means for stochastic LLM output (see § Reproducibility)
- [x] Hub-card / `owner-verify` residual **dropped** 2026-08-07 — ship on documented Hub/profile `licence=` fields + [NOTICE](../../NOTICE); no further owner Hub-card pass tracked

## Telemetry / remote processing

TranscriptX analysis runs **locally** on the user’s machine (or local Docker). There is **no product telemetry** and **no remote analysis SaaS path** in 1.0 scope.

Remote network activity occurs only when the user (or install profile) explicitly enables it, for example:

- Hugging Face / spaCy **model downloads** on first use
- Optional **Ollama** (typically local; user-configured host)
- Optional dependency / image pulls during install

Default Docker Compose binds the GUI to loopback — see [SECURITY.md](../../SECURITY.md).

## Reproducibility (LLM)

For stochastic LLM modules (`determinism_tier` T2):

- **Byte-identical transcript reproduction is not claimed** across runs, models, or temperatures.
- Artifacts should carry **provenance** where available: prompt version, model id, provider.
- Deterministic modules (T0/T1) remain the basis for comparable longitudinal metrics.
- “Re-run with same settings” is best-effort for LLM surfaces; treat outputs as **drafts requiring human review** (action items banner).

## AI output labelling

User-facing LLM surfaces show a **Local AI** badge (and action-items keep the human-review caption). Deterministic summaries are badged **Deterministic** on Overview when they win precedence.

## Voice / speaker-identity privacy

Authoritative copy: `VOICE_PRIVACY_USER_NOTICE` in `transcriptx.core.speaker_profiles.voice.privacy` (pinned by `PRIVACY_NOTICE_VERSION = voice_privacy_notice.v2`). Shown in Settings → Speakers before enable. Embeddings stay on-host under `speaker_profiles/voice`; revoke deletes evidence.

## Model / dependency matrix

Sourced from [runtime/models.md](../runtime/models.md) defaults and pinned HF profile `licence=` fields in `hf_text_classification/profiles.py`. Not legal advice; identifiers follow documented Hub/profile fields.

| Component | Licence | Download / gated? | Privacy notes | 1.0 posture |
|-----------|---------|-------------------|---------------|-------------|
| spaCy `en_core_web_md` (default) | spaCy model licence (see spaCy / model card) | Docker preinstalls sm/md/lg; others download when enabled | Local NLP; no remote call once installed | Ship |
| spaCy `en_core_web_lg` / `en_core_web_trf` (optional upgrades) | spaCy model licence | Download on first use when enabled | Same | Optional |
| `sentence-transformers/all-MiniLM-L6-v2` (semantic / echoes / BERTopic / KeyBERT default) | Apache-2.0 (Hub card / typical) | Hugging Face Hub download when enabled | Local embeddings | Ship |
| `sentence-transformers/all-mpnet-base-v2` (higher-accuracy option) | Apache-2.0 (Hub card / typical) | Hub download when enabled | Local embeddings | Optional |
| NRCLex vocabulary (`emotion` lexical) | See NRCLex / NRC emotion lexicon terms | Via `emotion_lexical` extra | Lexicon association; not a neural model | Ship |
| Contextual emotion profile `contextual_hartmann_distilroberta_v1` (`j-hartmann/emotion-english-distilroberta-base`, SHA `0e1cd914…`) | **Apache-2.0** (profile `licence=`) | Hub download; pinned revision; experimental | Local classifier; experimental channel | Ship (experimental) |
| Fine-grained emotion profile `fine_grained_samlowe_go_emotions_v1` (`SamLowe/roberta-base-go_emotions`, SHA `d750483…`) | **MIT** (profile `licence=`) | Hub download; pinned revision; experimental | Local classifier; experimental channel | Ship (experimental) |
| Sentiment VADER (default) | NLTK / VADER terms | Bundled NLTK data | Lexicon; local | Ship |
| Sentiment transformers option `cardiffnlp/twitter-roberta-base-sentiment-latest` | See Hub model card | Hub download when `sentiment_backend=transformers` | Local classifier | Optional |
| Dialogue acts (heuristic default) | N/A (rule/heuristic) | None | No model download | Ship as heuristic |
| Topic modeling LDA/NMF (sklearn) | sklearn / SciPy stack | None beyond install | Local | Ship |
| BERTopic stack | See BERTopic / UMAP / HDBSCAN deps | Embedding model as above | Local; heavy | Optional (`[bertopic]` / `[full]`) |
| Ollama LLM modules (optional) | Model-dependent (user-chosen Ollama models) | User pulls models into Ollama | Local when Ollama is local; label AI outputs | Optional — document |
| Voice / speaker-match embeddings (ECAPA / `[voice]`) | See SpeechBrain / model cards | Optional extras; may download | **Speaker-identity sensitive** — privacy notice v2 | Optional (`[voice]`) |

### NOTICE

User-facing third-party notice: repository root [NOTICE](../../NOTICE) (**0.9.7**; Hub-card residual dropped 2026-08-07). Licence identifiers follow documented Hub/profile fields.

Known limitations for users: [known_limitations.md](../known_limitations.md).
