Type: PRODUCT
Authority: self

# Install profiles matrix (1.0)

**Status:** audited for **0.9.4**  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §9  
**Authoritative verification cells:** [install_verification_matrix.md](../runtime/install_verification_matrix.md)

Do **not** invent `basic` / `llm` marketing names until the dependency graph matches. Runtime install markers today are **`core` | `full` only** (plus optional extras and a dedicated **`[web]`** GUI extra).

## Ownership summary (0.9.4)

| Concern | Owner | Not owned by |
|---------|-------|--------------|
| Streamlit GUI | `[web]` extra; Docker / `requirements.txt` / `./transcriptx.sh` | `[full]` (analysis extras only) |
| YAKE / KeyBERT | `[keyphrases]` + `[full]`; also in `requirements.txt` (Docker) | — |
| Playwright | `[maps]` (+ Docker) for optional NER map PNG | Streamlit GUI |
| `speaker_match` | `[speaker_match]` + `[full]`; SpeechBrain in Docker | — |

## Proposed user-facing profiles

| Profile | Install path | Capabilities | 1.0 status |
|---------|--------------|--------------|------------|
| **Docker full analysis** (recommended) | Compose + image from `requirements.txt` | GUI + full analysis stack; spaCy baked; YAKE/KeyBERT; CPU on Mac override | **Supported** — verify clean |
| **Docker + local AI** | Above + host Ollama via `host.docker.internal` | LLM modules / Corrections discovery | **Supported** |
| **Native full** | `./transcriptx.sh` / `requirements.txt` + editable; or `pip install -e ".[full,web]"` | GUI + near-Docker deps; CUDA available unless `TRANSCRIPTX_FORCE_CPU=1` | **Candidate** — confirm via clean-env matrix |
| **Native + local AI** | Native full + Ollama | Same + LLM | **Candidate** — follows native-full |
| **Voice / speaker match** | `[voice]` / `[speaker_match]` or Docker subset | Prosody + local ECAPA match | **Optional supported** |
| **Core analysis API** | `pip install -e .` | Library/API without Streamlit | **Developer/secondary** — must not claim “full app” |
| **Developer / test** | `.[dev]` (+ `nlp`) | CI lanes | **Contributor** |
| **Air-gap** | Any + `TRANSCRIPTX_DISABLE_DOWNLOADS=1` + prebaked caches | Offline inference | **Documented profile** |

## Capability matrix (summary)

| Capability | Docker `requirements.txt` | `.[full,web]` | `.[full]` only | `.[web]` only | Core `-e .` |
|------------|---------------------------|---------------|----------------|---------------|-------------|
| Streamlit GUI | yes | yes | **no** | yes | no |
| spaCy NLP | yes (image bake) | via `[nlp]` in full | via full | no | no |
| Voice / openSMILE | yes | yes | yes | no | no |
| Speaker match | yes (speechbrain) | yes | yes | no | no |
| Keyphrases YAKE/KeyBERT | yes (0.9.4+) | yes | yes | no | noun-chunks only if module runs |
| Maps + Playwright PNG | yes | yes | yes | no | no |
| BERTopic | yes | yes (base+full) | yes | base may include | base may include |

## Audit items (0.9.4)

- [x] Streamlit ownership (`[web]`; not in `[full]`)
- [x] Clarify `.[full]` ≠ Docker / `requirements.txt` / launcher
- [x] `keyphrases` YAKE/KeyBERT in Docker `requirements.txt`
- [x] `speaker_match` matrix cell
- [x] Auto-install hints use editable git checkout wording (not PyPI)
- [x] `transcriptx.sh` CUDA honesty (`TRANSCRIPTX_FORCE_CPU=1` opt-in)
- [x] Playwright: `[maps]` / Docker only; not Streamlit GUI
- [x] Capability matrix per profile
- [x] `setup_env.sh` removed (0.9.1); checklist closed

## Notes

Docker production image installs `requirements.txt` under `constraints.txt` then the wheel — **not** equivalent to `pip install -e ".[full]"` unless inventories are verified equal. For a native GUI matching Docker more closely, prefer `./transcriptx.sh` or `pip install -e ".[full,web]"`.
