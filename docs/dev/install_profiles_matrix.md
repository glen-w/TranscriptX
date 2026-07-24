Type: PRODUCT
Authority: self

# Install profiles matrix (1.0)

**Status:** planning  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §9  
**Authoritative verification cells:** [install_verification_matrix.md](../runtime/install_verification_matrix.md)

Do **not** invent `basic` / `llm` marketing names until the dependency graph matches. Runtime install markers today are **`core` | `full` only**.

## Proposed user-facing profiles

| Profile | Install path | Capabilities | 1.0 status |
|---------|--------------|--------------|------------|
| **Docker full analysis** (recommended) | Compose + image from `requirements.txt` | GUI + full analysis stack; spaCy baked; CPU on Mac override | **Supported** — verify clean |
| **Docker + local AI** | Above + host Ollama via `host.docker.internal` | LLM modules / Corrections discovery | **Supported** |
| **Native full** | `./transcriptx.sh` / requirements.txt + editable | GUI + near-Docker deps; honest CPU/CUDA/MPS matrix | **Candidate** — confirm via clean-env matrix |
| **Native + local AI** | Native full + Ollama | Same + LLM | **Candidate** — follows native-full |
| **Voice / speaker match** | `[voice]` / `[speaker_match]` or Docker subset | Prosody + local ECAPA match | **Optional supported** |
| **Core analysis API** | `pip install -e .` | Library/API without assuming Streamlit | **Developer/secondary** — must not claim “full app” |
| **Developer / test** | `.[dev]` (+ `nlp`) | CI lanes | **Contributor** |
| **Air-gap** | Any + `TRANSCRIPTX_DISABLE_DOWNLOADS=1` + prebaked caches | Offline inference | **Documented profile** |

## Open audit items

- [ ] Streamlit ownership (not in `[full]`)
- [ ] Clarify `.[full]` ≠ Docker / `requirements.txt` / launcher
- [ ] Missing `keyphrases` in Docker (if still true)
- [ ] `speaker_match` matrix cell
- [ ] Auto-install hints using PyPI name
- [ ] `transcriptx.sh` CUDA honesty
- [ ] Playwright: only where a supported runtime feature needs it
- [ ] Capability matrix per profile

## Notes

Docker production image installs `requirements.txt` under `constraints.txt` then the wheel — **not** equivalent to `pip install -e ".[full]"` unless inventories are verified equal.
