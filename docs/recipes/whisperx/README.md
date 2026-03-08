# WhisperX standalone (optional reference recipe)

These files are **optional standalone reference examples** for running WhisperX independently. They are **not** part of the TranscriptX runtime—TranscriptX is analysis-only and does not orchestrate WhisperX. Use any tool that produces compatible transcript JSON; WhisperX is one example.

Use them to generate diarized transcript JSON that you can then **canonicalize** and **analyze** with TranscriptX:

```bash
# 1. Generate transcript (e.g. with WhisperX Docker)
# 2. Canonicalize (optional but recommended)
transcriptx transcript canonicalize --in whisperx.json --out meeting_transcriptx.json
# 3. Analyze
transcriptx analyze --transcript-file meeting_transcriptx.json
```

## Configure WhisperX

1. Copy the env example and set your values:
   ```bash
   cp whisperx.env.example whisperx.env
   ```
2. Edit `whisperx.env`: set `HF_TOKEN` for diarization and gated models.
3. Never commit `whisperx.env` (add it to `.gitignore` if using this recipe in your repo).

**Single source of truth for env-configurable settings:** `whisperx.env.example` in this directory. The table below maps every former TranscriptX `TranscriptionConfig` field to its new mechanism so no capability is lost.

### TranscriptionConfig migration table

Every former `TranscriptionConfig` field is mapped below; if you add a new knob, update this table.

| Old TranscriptX field     | Old env var                      | New mechanism                | Default                     | Notes                                                                 |
|---------------------------|----------------------------------|-------------------------------|-----------------------------|-----------------------------------------------------------------------|
| `model_name`              | `TRANSCRIPTX_MODEL_NAME`        | `WHISPERX_MODEL` env var      | `large-v2`                  | Set in `whisperx.env`                                                 |
| `language`                | `TRANSCRIPTX_LANGUAGE`          | `WHISPERX_LANGUAGE` env var   | `en`                        | Set in `whisperx.env`                                                 |
| `compute_type`            | `TRANSCRIPTX_COMPUTE_TYPE`      | `WHISPERX_COMPUTE_TYPE` env   | `float16`                   | `float16` for GPU, `int8` for CPU                                     |
| `diarize`                 | (config only)                    | `WHISPERX_DIARIZE` env var    | `true`                      | Requires `HF_TOKEN`                                                    |
| `huggingface_token`       | `HF_TOKEN` / `TRANSCRIPTX_HUGGINGFACE_TOKEN` | `HF_TOKEN` env var | (none)                      | Required for diarization + gated models                               |
| `batch_size`              | (config only)                    | WhisperX CLI: `--batch_size 16` | `16`                     | Not env-configurable; pass via docker exec command                    |
| `min_speakers`            | (config only)                    | WhisperX CLI: `--min_speakers 1` | `1`                      | Not env-configurable; pass via docker exec command                   |
| `max_speakers`            | (config only)                    | WhisperX CLI: `--max_speakers 20` | `20` (or omit)           | Not env-configurable; pass via docker exec command                    |
| `model_download_policy`   | (config only)                    | No 1:1 equivalent             | `require_token`             | Gated models require `HF_TOKEN`; set or omit `HF_TOKEN`.              |
| (device — not in config)  | (not in config)                  | `WHISPERX_DEVICE` env var     | `cpu`                       | `cuda` for GPU                                                        |

## Run WhisperX

**Using Compose (from this directory):**

```bash
cd docs/recipes/whisperx
cp whisperx.env.example whisperx.env
# Edit whisperx.env and set HF_TOKEN
docker compose -f docker-compose.whisperx.yml up -d
# Run transcription via docker exec; see WhisperX docs for exact command.
```

**Using a single `docker run` (snippet for reference):**

Override the image entrypoint and run `whisperx` explicitly in a shell so the audio path and flags are passed correctly:

```bash
docker run --rm --entrypoint /bin/bash \
  -v "$(pwd)/data/recordings:/data/input:ro" -v "$(pwd)/data/transcripts:/data/output" \
  --env-file whisperx.env \
  ghcr.io/jim60105/whisperx:no_model \
  -c "whisperx /data/input/your_audio.wav --output_dir /data/output --language en --diarize"
```

Replace `your_audio.wav` with your file (e.g. `260225_cursor_presentation.mp3`). With this image, passing arguments directly after the image name does not reach `whisperx`; use the `--entrypoint /bin/bash` form above.

Adjust paths and WhisperX CLI flags to match your setup. Output format: WhisperX JSON; then use `transcriptx transcript canonicalize` to produce canonical JSON for analysis.

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
