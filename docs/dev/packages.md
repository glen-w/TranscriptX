# Packages used

Pin source of truth is [`pyproject.toml`](../../pyproject.toml) (`[project.dependencies]` and `[project.optional-dependencies]`). This page is a map, not a second pin list.

CVE / waiver policy: [dependency_audit.md](dependency_audit.md). Analysis model IDs: [models.md](../runtime/models.md). Install profiles: [install_profiles_matrix.md](install_profiles_matrix.md).

## Core wheel

`pip install transcriptx` (no extras) is the analysis core plus the Streamlit launcher entry point. It deliberately omits compiled NLP / voice / BERTopic stacks so a clean host install is not blocked by `llvmlite` / CUDA wheels. Exact pins: `pyproject.toml` `[project.dependencies]`.

The GUI extra is separate: Streamlit is **`[web]`**, not in `[full]`. Docker / `transcriptx.sh` install the GUI via `requirements.txt`.

## Install extras

| Extra | What it is for |
|-------|----------------|
| `web` | Streamlit GUI. Not included in `[full]`. |
| `nlp` / `ner` | spaCy NER (`ner` is an alias; modules require `nlp`). |
| `emotion_lexical` | NRCLex lexical emotion. |
| `emotion_transformers` | Torch + Transformers contextual / fine-grained emotion. |
| `emotion` | Compatibility union of the two emotion extras. |
| `voice` | pyannote / openSMILE / librosa analysis audio. |
| `speaker_match` | SpeechBrain speaker embeddings (separate from analysis `[voice]`). |
| `keyphrases` | YAKE / KeyBERT (noun-chunks still run without this extra). |
| `bertopic` | BERTopic + hdbscan + umap-learn. Optional; see [bertopic_optional_module.md](bertopic_optional_module.md). |
| `maps` | Folium / geopy / Playwright for NER map HTML→PNG. |
| `visualization` | matplotlib, seaborn, wordcloud, ebooklib (Overview EPUB). |
| `plotly` | Plotly. |
| `full` | Union of the analysis extras above (not `[web]`, `[dev]`, or `[docs]`). |
| `dev` | pytest, linters, pre-commit, plus matplotlib/seaborn/geopy for smoke tests. |
| `docs` | Sphinx, MyST, Furo. |

## Workspace package

[`packages/transcriptx_workspaces`](../../packages/transcriptx_workspaces/README.md) is the Theme C Streamlit Components v2 package (Speaker ID workspace). Install alongside `[web]`:

```bash
pip install -e packages/transcriptx_workspaces
```

If it is not installed, Speaker ID falls through to the classic UI. See [theme_c_workspaces_ccv2.md](theme_c_workspaces_ccv2.md).
