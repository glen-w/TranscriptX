# Installation

**Most people:** Docker, then [First analysis](../workflows/first-analysis.md). This page is the normal install path. Pip extras, install profiles, environment variables, and gates are in [Installation details](installation-advanced.md).

## Docker (recommended)

No local Python required. Copy `.env.example` to `.env`, set `HOST_RECORDINGS_DIR` to an absolute path **outside this repository**, then:

```bash
docker compose up transcriptx-web
```

Open http://localhost:8501. The first run builds the image. Container notes: [docker.md](docker.md).

## Native (from this repository)

**Python 3.10–3.12.** The package is **not on PyPI** — clone the repo and install from there.

The launcher creates a `.transcriptx` virtual environment, installs dependencies, and starts the web UI:

```bash
./transcriptx.sh
```

Open http://localhost:8501. Core-only: `TRANSCRIPTX_CORE=1 ./transcriptx.sh`.

If you use a native install and want language features such as topic modeling, the launcher’s fast path includes the NLP extra. Download the English model **once**:

```bash
python -m spacy download en_core_web_md
```

Both the extra and the model are required for those modules. Docker images already include this.

## After install

1. Follow [First analysis](../workflows/first-analysis.md).
2. Bring a file you already have, or generate one from audio — [Transcription](transcription.md).
3. On **Run Analysis**, keep **Balanced** unless you have a reason not to. Edit Quick / Balanced / Thorough under **Settings → Analysis** — [Settings](settings.md#analysis-presets).

## Troubleshooting

- **"No module named …" after a native install** — install dependencies first (`pip install -r requirements.txt` then `pip install -e .`), or reinstall with the extras you need (`pip install -e ".[full,web]"`). See [Installation details](installation-advanced.md).
- **spaCy model errors** — the language model is a separate download from the NLP extra. Run `python -m spacy download en_core_web_md`.
- **GPU / Apple Silicon** — Docker on Mac is CPU-only (the predictable path). Native MPS is supported-with-caveats; if a model fails, retry with `TRANSCRIPTX_FORCE_CPU=1 ./transcriptx.sh`. See [known limitations](../known_limitations.md).
- **Offline / blocked downloads** — [environment variables](installation-advanced.md#environment-variables).

## Advanced

- [Installation details](installation-advanced.md) — extras, install profiles, gates, environment variables, Streamlit flags
- [Docker](docker.md) — Compose, volumes, CPU vs GPU images
- [Developer quick start](../developer_quickstart.md)
