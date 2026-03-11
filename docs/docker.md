# Docker

**Docker Compose is the recommended way** to run TranscriptX in containers (no local Python required). The Streamlit web interface runs inside the container with a mounted data directory.

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

Multi-arch (e.g. for publishing):

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t transcriptx:latest .
```

The image includes the spaCy language models (`en_core_web_md` and `en_core_web_sm`), so NLP modules (topic modeling, NER, etc.) work out of the box—no need to run `python -m spacy download` inside the container.

**Apple Silicon (M1/M2/M3):** If the arm64 build fails or you want maximum compatibility with CPU/torch wheels, build and run the amd64 image under emulation:

```bash
docker buildx build --platform linux/amd64 --load -t transcriptx:amd64 .
docker run --rm -v "$(pwd)/data:/data" --platform linux/amd64 -p 8501:8501 transcriptx:amd64
```

### Primary commands: Web interface

**Start the web interface (port 8501):**

```bash
docker compose up transcriptx-web
```

Then open http://localhost:8501 in your browser.

**Speaker Studio (instant audio playback, port 8502):**

```bash
docker compose up transcriptx-studio
```

Then open http://localhost:8502.

**Both services:**

```bash
docker compose up
```

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
| Web interface | `docker compose up transcriptx-web` → http://localhost:8501 |
| Speaker Studio | `docker compose up transcriptx-studio` → http://localhost:8502 |
| Both | `docker compose up` |
| Custom host/port | `docker run --rm -p 8502:8502 transcriptx:latest --host 0.0.0.0 --port 8502` |

## Volume layout

Mount your data at `/data`:

```yaml
volumes:
  - ./data:/data
```

Recommended layout under `./data`:

```
data/
  recordings/    ← source WAV/MP3 files
  transcripts/   ← JSON transcripts
  outputs/       ← analysis run outputs
```

Optional separate mounts for large libraries:

```yaml
volumes:
  - ./data:/data
  - /path/to/recordings:/recordings
  - /path/to/transcripts:/transcripts
```

Then set environment variables:
```
TRANSCRIPTX_RECORDINGS_DIR=/recordings
TRANSCRIPTX_TRANSCRIPTS_DIR=/transcripts
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSCRIPTX_DATA_DIR` | `/data` | Base data directory inside container |
| `TRANSCRIPTX_RECORDINGS_DIR` | `$DATA_DIR/recordings` | Source audio |
| `TRANSCRIPTX_TRANSCRIPTS_DIR` | `$DATA_DIR/transcripts` | Transcript JSON files |
| `TRANSCRIPTX_OUTPUT_DIR` | `$DATA_DIR/outputs` | Analysis outputs |
| `TRANSCRIPTX_DISABLE_DOWNLOADS` | `1` | Disable model/resource downloads |
| `TRANSCRIPTX_HOST` | `0.0.0.0` | Streamlit bind host |
| `TRANSCRIPTX_PORT` | `8501` | Streamlit port |

## Health check

The compose file includes a health check that pings the Streamlit health endpoint:

```bash
docker compose ps   # shows health status
```

## Pitfalls

- **Port conflict:** If 8501 is taken, override with `--port 8502` or set `TRANSCRIPTX_PORT`.
- **Permissions:** Ensure the `./data` directory is writable by the UID/GID used in compose.
- **Model downloads:** Set `TRANSCRIPTX_DISABLE_DOWNLOADS=0` if you need to download ML models at runtime (the image includes spaCy but not all optional models).
