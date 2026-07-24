Type: GUIDE
Authority: docs/runtime/installation.md

# Install verification matrix

**Authority:** This document is the authoritative install-verification matrix for TranscriptX **0.9.4**. Do not advertise an install command that cannot pass its stated cell.

**Distribution reality:** versioned **git tags** + **Docker Compose** image. The package is **not published on PyPI**. Bare `pip install transcriptx` from PyPI will fail and must not be advertised as a primary install path.

**Repository:** https://github.com/glen-w/TranscriptX

## Supported interpreters

| Python | Status |
|--------|--------|
| 3.10 | Supported (CI matrix) |
| 3.11 | Supported (CI matrix) |
| 3.12 | Supported (CI matrix) |
| ≤3.9 or ≥3.13 | Unsupported (`requires-python = ">=3.10,<3.13"`) |

## Supported operating systems (claimed)

| OS | Status | Notes |
|----|--------|-------|
| macOS (Apple Silicon / Intel) | Supported-with-caveats | Prefer **Docker CPU** for predictable installs. Native Apple **MPS** is not universally validated for every optional model — see [installation.md](installation.md). If MPS init or model execution fails, use `TRANSCRIPTX_FORCE_CPU=1`. Host `.[bertopic]`/`[full]` may fail when `llvmlite` wheels are unavailable; Docker `image_pip_check` remains the fuller-stack image proof. |
| Linux (x86_64 / aarch64) | Supported | GPU via NVIDIA toolkit when available |
| Windows | Best-effort | Native Windows is not a primary CI target; WSL2 + Docker recommended |

## Install paths

| Cell | Command / proof | Expected result |
|------|-----------------|-----------------|
| **Core (from git)** | `python -m venv .venv && source .venv/bin/activate && pip install -e .` | Import succeeds |
| **Core + dev** | `pip install -e ".[dev]"` | Dev tools + pytest stack; `make test-smoke` (charting needs matplotlib/geopy from the `dev` extra; spaCy-gated modules skip unless `.[nlp]` is also installed) |
| **Core + dev + nlp** | `pip install -e ".[dev,nlp]"` then `python -m spacy download en_core_web_md` | Same as Core+dev plus spaCy-gated smoke (`make test-smoke-nlp`; CI `tests-nlp` job) |
| **docs** | `pip install -e ".[docs]"` | Docs build extras |
| **ner** | `pip install -e ".[ner]"` | NER optional deps |
| **emotion_lexical** | `pip install -e ".[emotion_lexical]"` | Lexical emotion deps |
| **emotion_transformers** | `pip install -e ".[emotion_transformers]"` | Transformer emotion deps |
| **emotion** | `pip install -e ".[emotion]"` | Combined emotion extras |
| **voice** | `pip install -e ".[voice]"` | Voice / audio analysis deps |
| **speaker_match** | `pip install -e ".[speaker_match]"` | Local ECAPA / SpeechBrain speaker-match deps (`import speechbrain`) |
| **nlp** | `pip install -e ".[nlp]"` then `python -m spacy download en_core_web_md` | NLP + spaCy model |
| **bertopic** | `pip install -e ".[bertopic]"` | Optional BERTopic stack (`bertopic`/`hdbscan`/`umap-learn`); also in `[full]` / Docker |
| **keyphrases** | `pip install -e ".[keyphrases]"` | Optional YAKE + KeyBERT for `keyphrases` module (noun-chunks path works without this extra) |
| **maps** | `pip install -e ".[maps]"` | Maps extras; Playwright for optional HTML→PNG (not required for Streamlit GUI) |
| **visualization** | `pip install -e ".[visualization]"` | Viz extras |
| **plotly** | `pip install -e ".[plotly]"` | Plotly extras |
| **web** | `pip install -e ".[web]"` | Streamlit GUI only (not included in `[full]`) |
| **full** | `pip install -e ".[full]"` | All optional **analysis** extras; may fail on some hosts (e.g. llvmlite) — does **not** install Streamlit |
| **full + web (native GUI)** | `pip install -e ".[full,web]"` | Analysis extras + Streamlit; closest editable match to Docker GUI |
| **Docker production image** | `docker compose -f docker-compose.yml build` then `make docker-smoke` | **Production-image installation proof** (wheel + `requirements.txt` under `constraints.txt`). This is **not** `pip install -e '.[full]'` unless inventories are verified equal |
| **PyPI bare** | `pip install transcriptx` | **Not supported** — package is not on PyPI |

## Fresh-clone evidence (release bundle)

At tag time, record:

1. Clone of the exact release commit
2. Core editable install on one supported Python
3. Docker production-image build + smoke
4. Pointers to CI artefacts for the commit (test matrix + release-checks)

See `docs/dev/release_governance.md`.
