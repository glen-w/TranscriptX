# WhisperX standalone (optional reference recipe)

Use this when you want diarized WhisperX JSON, then import it into TranscriptX. These files are **optional standalone examples**. They are **not** part of the TranscriptX runtime — TranscriptX does not orchestrate WhisperX. Any tool that produces compatible transcript JSON is fine; WhisperX is one example.

## What this is for

1. Generate transcript JSON with WhisperX (Docker, or the Transcribe Audio command generator).
2. In TranscriptX, **Import Transcript** and upload that JSON.
3. Run analysis in the web UI.

## GUI path (recommended)

1. Open **Transcribe Audio** in TranscriptX.
2. Choose **WhisperX Docker (external recipe)**, set input/output folders, model, language, device, and optional min/max speakers.
3. Copy the generated `docker run` command and execute it on a Linux/GPU host (not inside `transcriptx-web`).
4. Import the resulting **WhisperX JSON** via **Import Transcript**.

## Configure WhisperX (compose / env)

1. Copy the env example and set your values:
   ```bash
   cp whisperx.env.example whisperx.env
   ```
2. Edit `whisperx.env`: set `HF_TOKEN` for diarization and gated models.
3. Never commit `whisperx.env`.

Env-configurable settings live in `whisperx.env.example` in this directory. A historical map from the old in-app `TranscriptionConfig` fields to these env vars is in the [archive migration table](https://github.com/glen-w/TranscriptX/blob/main/docs/archive/migrations/whisperx_transcriptionconfig.md) (not required for new setups; not in the hosted guide).

## Run WhisperX

**Using Compose (from this directory):**

```bash
cd docs/recipes/whisperx
export HOST_RECORDINGS_DIR=/path/to/your/recordings   # host folder outside the git clone (required)
cp whisperx.env.example whisperx.env
# Edit whisperx.env and set HF_TOKEN
docker compose -f docker-compose.whisperx.yml up -d
# Run transcription via docker exec; see WhisperX docs for exact command.
```

**Using a single `docker run` (snippet for reference):**

Override the image entrypoint and run `whisperx` explicitly in a shell so the audio path and flags are passed correctly:

```bash
export HOST_RECORDINGS_DIR=/path/to/your/recordings   # outside the git clone
docker run --rm --entrypoint /bin/bash \
  -v "$HOST_RECORDINGS_DIR:/data/input:ro" -v "$(pwd)/data/transcripts:/data/output" \
  --env-file whisperx.env \
  ghcr.io/jim60105/whisperx:no_model \
  -c "whisperx /data/input/your_audio.wav --output_dir /data/output --language en --diarize"
```

Replace `your_audio.wav` with your file (e.g. `260225_cursor_presentation.mp3`). With this image, passing arguments directly after the image name does not reach `whisperx`; use the `--entrypoint /bin/bash` form above.

Adjust paths and WhisperX CLI flags to match your setup. Output format: WhisperX JSON; then **Import Transcript** (or the Python import API in [host-stt.md](../../runtime/host-stt.md#python-api)).

## Python import (optional)

From the repo root with your environment active:

```python
from pathlib import Path

from transcriptx.io.managed_import_workflow import run_managed_import_workflow

result = run_managed_import_workflow(
    Path("path/to/whisperx.json"),
    overwrite=False,
)
print(result.json_path)
print(result.sidecar_path)
```

Then analyse in the web UI or via `run_analysis(AnalysisRequest(...))` (see [host-stt.md](../../runtime/host-stt.md#python-api)).

## Troubleshooting

### 403 / GatedRepoError when using `--diarize`

If you see:

- `No --hf_token provided, needs to be saved in environment variable`
- `Could not download Pipeline from pyannote/speaker-diarization-community-1`
- `GatedRepoError: 403 Client Error` or "repository is private or gated"

the diarization model requires a Hugging Face token and acceptance of its terms:

1. **Accept model terms:** Open [pyannote/speaker-diarization-community-1](https://hf.co/pyannote/speaker-diarization-community-1) and accept the user conditions.
2. **Create a token:** Go to [Hugging Face → Settings → Access Tokens](https://hf.co/settings/tokens), create a token (read access is enough).
3. **Pass the token:** In `whisperx.env` set `HF_TOKEN=hf_xxxxxxxx` (your real token). Ensure your `docker run` or Compose command uses `--env-file whisperx.env` so the container receives `HF_TOKEN`. WhisperX reads it for diarization.

If you prefer not to use diarization, run without `--diarize` (no token needed).
