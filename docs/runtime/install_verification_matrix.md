Type: GUIDE
Authority: docs/runtime/installation.md

# Install verification matrix

**Authority:** This document is the authoritative install-verification matrix for TranscriptX **0.9.1**. Do not advertise an install command that cannot pass its stated cell.

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
| macOS (Apple Silicon / Intel) | Supported | Prefer Docker CPU torch variant or native venv; Docker cannot use host GPU |
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
| **nlp** | `pip install -e ".[nlp]"` then `python -m spacy download en_core_web_md` | NLP + spaCy model |
| **bertopic** | `pip install -e ".[bertopic]"` | Compatibility alias (BERTopic may already be in core) |
| **keyphrases** | `pip install -e ".[keyphrases]"` | Optional YAKE + KeyBERT for `keyphrases` module (noun-chunks path works without this extra) |
| **maps** | `pip install -e ".[maps]"` | Maps extras |
| **visualization** | `pip install -e ".[visualization]"` | Viz extras |
| **plotly** | `pip install -e ".[plotly]"` | Plotly extras |
| **full** | `pip install -e ".[full]"` | All optional extras; may fail on some hosts (e.g. llvmlite) — not a Wave 0 host gate |
| **Docker production image** | `docker compose -f docker-compose.yml build` then `make docker-smoke` | **Production-image installation proof** (wheel + `requirements.txt` under `constraints.txt`). This is **not** `pip install '.[full]'` unless inventories are verified equal |
| **PyPI bare** | `pip install transcriptx` | **Not supported** — package is not on PyPI |

## Fresh-clone evidence (release bundle)

At tag time, record:

1. Clone of the exact release commit
2. Core editable install on one supported Python
3. Docker production-image build + smoke
4. Pointers to CI artefacts for the commit (test matrix + release-checks)

See `docs/dev/release_governance.md`.
