Type: GUIDE
Authority: runtime/STORAGE.md

# Docker

Operational guide only. For authoritative storage and metadata structure, see `STORAGE.md`. For behavior and invariants, see CONTRACT documents.

**Docker Compose is the recommended way** to run TranscriptX in containers (no local Python required). The Streamlit web interface runs inside the container with a mounted data directory.

This guide describes container behavior and operational layouts only. Canonical storage, output, and run-truth rules live in:

- `docs/runtime/STORAGE.md`
- `docs/contracts/output-contract-v1.md`
- `docs/run_outcome_contract.md`

TranscriptX is **analysis-only**; it does not run WhisperX or any transcription engine inside Docker. Bring your own transcript JSON (see [transcription.md](transcription.md) for how to generate compatible transcripts).

## Non-root /data write access

The default compose runs the `transcriptx-web` service as your host user (`user: "${UID:-1000}:${GID:-1000}"`) so that files written under the mounted `./data` volume are owned by you.

- **Dev / quick start:** If `/data` is not writable (e.g. permission denied), make the host directory writable: `chmod -R a+w data/` (or create `data` and then run compose).
- **Production:** Use the same `user: "${UID:-1000}:${GID:-1000}"` so the container runs as a known UID/GID; ensure the host `./data` is owned by that user or is group-writable.

## Quickstart

### Build

```bash
docker build -t transcriptx:latest .
```

Set **`TRANSCRIPTX_TORCH_VARIANT`** at build time to control which PyTorch wheels are installed:

| Value | When to use |
|-------|-------------|
| `default` (unset) | Linux with NVIDIA GPU (`nvidia-container-toolkit`). Pulls CUDA wheels from PyPI on arm64. |
| `cpu` | Mac / Apple Silicon, or any CPU-only host. Skips 500MB+ NVIDIA deps; uses [PyTorch CPU wheels](https://download.pytorch.org/whl/cpu). |

With Compose (reads from `.env` or `docker-compose.override.yml`):

```bash
# Mac local dev (docker-compose.override.yml sets cpu by default)
docker compose build

# Explicit CPU build
TRANSCRIPTX_TORCH_VARIANT=cpu docker compose build

# GPU-oriented build (Linux)
TRANSCRIPTX_TORCH_VARIANT=default docker compose build
```

Plain `docker build`:

```bash
docker build --build-arg TRANSCRIPTX_TORCH_VARIANT=cpu -t transcriptx:latest .
```

Multi-arch (e.g. for publishing):

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t transcriptx:latest .
```

The image includes the spaCy language models (`en_core_web_sm`, `en_core_web_md`, and `en_core_web_lg`), so NLP modules (topic modeling, NER, etc.) work out of the box—no need to run `python -m spacy download` inside the container.

**Apple Silicon (M1/M2/M3):** Prefer a CPU torch build — `docker-compose.override.yml` sets `TRANSCRIPTX_TORCH_VARIANT=cpu` for local dev. Docker on Mac cannot use GPU acceleration anyway. If arm64 builds still fail, you can build the amd64 image under emulation:

```bash
docker buildx build --platform linux/amd64 --load -t transcriptx:amd64 .
export HOST_RECORDINGS_DIR=/path/to/your/recordings   # outside the repo; same as in .env for compose
docker run --rm -v "$(pwd)/data:/data" -v "$HOST_RECORDINGS_DIR:/mnt/recordings" \
  -e TRANSCRIPTX_RECORDINGS_DIR=/mnt/recordings --platform linux/amd64 -p 8501:8501 transcriptx:amd64
```

### Primary commands: Web interface

**Start the web interface (port 8501):**

```bash
docker compose up transcriptx-web
```

Then open http://localhost:8501 in your browser.

You can also run `docker compose up` (without a service name) to start the web interface.

**Scripting / automation (one-off Python API):**

```bash
docker run --rm \
  -v "$(pwd)/data:/data" \
  -w /data \
  transcriptx:latest \
  python -c "
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis
from pathlib import Path

result = run_analysis(AnalysisRequest(
    transcript_path=Path('/data/transcripts/foo_transcriptx.json'),
    modules=['stats'],
))
print('success:', result.success)
"
```

### Operational modes

| Mode | Command |
|------|---------|
| Web interface | `docker compose up` or `docker compose up transcriptx-web` → http://localhost:8501 |
| Custom host/port | `docker run --rm -p 8501:8501 transcriptx:latest --host 0.0.0.0 --port 8501` |

## Volume layout

Compose mounts app working data at `/data` and maps host folders to container paths via `HOST_*` variables in `.env` (see `.env.example`):

```yaml
volumes:
  - ./data:/data
  - transcriptx_cache:/home/transcriptx/.cache
  - ${HOST_TRANSCRIPTS_DIR:-./data/transcripts}:/mnt/transcripts:ro
  - ${HOST_TRANSCRIPT_INBOX_DIR:-./data/transcript-inbox}:/mnt/transcript-inbox:ro
  - ${HOST_OUTPUT_DIR:-./data/outputs}:/mnt/outputs
  - ${HOST_RECORDINGS_DIR}:/mnt/recordings
  - ${HOST_RECORDINGS_DIR}/imports:/mnt/recordings/imports
  - ${HOST_WAV_BACKUP_DIR:-./data/backups/wav}:/mnt/wav
```

`HOST_RECORDINGS_DIR` is **required** in `.env` and must point at a host folder **outside the repository** (your source-audio library). Create `imports/` under that folder for uploads if needed.

| Host variable | Container path | App env (`TRANSCRIPTX_*`) | Notes |
|---------------|----------------|---------------------------|-------|
| (default) `./data` | `/data` | `TRANSCRIPTX_DATA_DIR=/data` | App cache, config copies, HF/Numba caches |
| `HOST_TRANSCRIPTS_DIR` (default `./data/transcripts`) | `/mnt/transcripts` | `TRANSCRIPTX_TRANSCRIPTS_DIR=/mnt/transcripts` | **Read-only** in base compose |
| `HOST_TRANSCRIPT_INBOX_DIR` (default `./data/transcript-inbox`) | `/mnt/transcript-inbox` | (scan path only) | External inbox for **Import all from folder**; not under managed transcripts |
| `HOST_OUTPUT_DIR` (default `./data/outputs`) | `/mnt/outputs` | `TRANSCRIPTX_OUTPUT_DIR=/mnt/outputs` | Analysis run outputs |
| `HOST_RECORDINGS_DIR` | `/mnt/recordings` | `TRANSCRIPTX_RECORDINGS_DIR=/mnt/recordings` | Source audio (read-only root) |
| `HOST_RECORDINGS_DIR/imports` | `/mnt/recordings/imports` | `TRANSCRIPTX_IMPORTS_DIR=/mnt/recordings/imports` | Writable uploads staging |
| `HOST_WAV_BACKUP_DIR` (default `./data/backups/wav`) | `/mnt/wav` | `TRANSCRIPTX_WAV_BACKUP_DIR=/mnt/wav` | WAV archive |

**Local dev override:** `docker-compose.override.yml` (optional, often gitignored) repeats these mounts but drops `:ro` on transcripts so the web UI can write speaker-map sidecars beside JSON files. For production-like read-only transcripts, use only `docker-compose.yml` or remove the override.

Canonical storage layout and invariants: [`docs/runtime/STORAGE.md`](../runtime/STORAGE.md).

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST_RECORDINGS_DIR` | (required in `.env`) | Host path to source audio library (outside repo) |
| `HOST_TRANSCRIPTS_DIR` | `./data/transcripts` | Host path mounted at `/mnt/transcripts` |
| `HOST_TRANSCRIPT_INBOX_DIR` | `./data/transcript-inbox` | Host path mounted at `/mnt/transcript-inbox` (folder-import inbox) |
| `HOST_OUTPUT_DIR` | `./data/outputs` | Host path mounted at `/mnt/outputs` |
| `HOST_WAV_BACKUP_DIR` | `./data/backups/wav` | Host path mounted at `/mnt/wav` |
| `STREAMLIT_SERVER_MAX_UPLOAD_SIZE` | `500` (in compose) | Max upload size in MB per file (Audio Merge, Audio Prep). Set in compose so the container allows 500 MB; without it Streamlit defaults to 200 MB. |
| `TRANSCRIPTX_DATA_DIR` | `/data` | Base data directory inside container |
| `TRANSCRIPTX_RECORDINGS_DIR` | `/mnt/recordings` (compose) | Source audio |
| `TRANSCRIPTX_IMPORTS_DIR` | `/mnt/recordings/imports` (compose) | Writable upload staging |
| `TRANSCRIPTX_TRANSCRIPTS_DIR` | `/mnt/transcripts` (compose) | Transcript JSON files |
| `TRANSCRIPTX_OUTPUT_DIR` | `/mnt/outputs` (compose) | Analysis outputs |
| `TRANSCRIPTX_WAV_BACKUP_DIR` | `/mnt/wav` (compose) | WAV archive |
| `TRANSCRIPTX_DISABLE_DOWNLOADS` | `0` | Enable model/resource downloads (`1` disables) |
| `TRANSCRIPTX_HOST` | `0.0.0.0` | Streamlit bind host |
| `TRANSCRIPTX_PORT` | `8501` | Streamlit port |

Optional **model overrides** (`TRANSCRIPTX_SPACY_MODEL`, `TRANSCRIPTX_SEMANTIC_MODEL`, etc.) and **LLM / Ollama** settings (`TRANSCRIPTX_LLM_ENABLED`, `TRANSCRIPTX_LLM_BASE_URL`, `TRANSCRIPTX_CORRECTIONS_LLM_ENABLED`, …) are passed from the host `.env` into the container. See [models.md](models.md), [llm.md](llm.md), and [corrections-llm.md](corrections-llm.md). On Mac/Windows Docker, point `TRANSCRIPTX_LLM_BASE_URL` at `http://host.docker.internal:11434` so the container can reach Ollama on the host. Local `docker-compose.override.yml` defaults LLM + Corrections Studio discovery on when those vars are unset.

## Health check

The compose file includes a health check that pings the Streamlit health endpoint:

```bash
docker compose ps   # shows health status
```

## Pitfalls

- **Port conflict:** If 8501 is taken, override with `--port 8502` or set `TRANSCRIPTX_PORT`.
- **Permissions:** Ensure the `./data` directory is writable by the UID/GID used in compose.
- **Model downloads:** Runtime downloads are enabled by default. Set `TRANSCRIPTX_DISABLE_DOWNLOADS=1` for offline/no-download runs and provide pre-populated caches as needed.
- **Upload "AxiosError: Network Error":** If the file uploader shows this for large files, the server limit or a reverse proxy may be blocking the request. Compose sets `STREAMLIT_SERVER_MAX_UPLOAD_SIZE=500`; if you use a proxy in front, increase its body size and timeouts (e.g. nginx `client_max_body_size` and `proxy_read_timeout`).
