# Whisper-WebUI (optional interoperability recipe)

Use this when you want a local webpage that transcribes audio, then import the subtitles into TranscriptX.

## What this is for

1. Deploy Whisper-WebUI (Docker below — recommended).
2. Open `http://127.0.0.1:7860`, upload audio, set model/language/diarization in the UI.
3. Download **SRT** or **WebVTT**.
4. In TranscriptX: **Import Transcript** → upload the subtitle file (optionally attach the recording).

### GUI path (via TranscriptX)

1. Open **Transcribe Audio** in TranscriptX.
2. Choose **Whisper-WebUI Docker (Gradio)**, set the outputs folder, port, and CPU vs CUDA.
3. Copy the generated deploy snippet and run it on the host.
4. Transcribe in the browser; import **SRT/VTT** via **Import Transcript**.

**Apple Silicon:** this container is expected to use **CPU** inference. Prefer **whispermlx** on the Mac host when speed matters. Details in [Apple Silicon](#apple-silicon) below.

## Docker (recommended)

Compose file in this directory binds **localhost only** and mounts models/outputs on the host. It does **not** enable NVIDIA by default (CPU path — including Apple Silicon).

From this directory:

```bash
export CLONE_DIR="${CLONE_DIR:-$HOME/Whisper-WebUI}"
export OUTDIR="${OUTDIR:-$HOME/whisper-webui-outputs}"
mkdir -p "$OUTDIR" "$CLONE_DIR/models" "$CLONE_DIR/outputs" "$CLONE_DIR/configs"

# Optional: export HF_TOKEN=… only if you will enable diarization in the UI.
docker compose -f docker-compose.whisper-webui.yml config   # validate; no image pull required for config
docker compose -f docker-compose.whisper-webui.yml up -d
# Open http://127.0.0.1:7860
```

### Pre-built image (`docker run`)

Same defaults as the Transcribe Audio command generator (localhost bind, pinned tag):

```bash
export CLONE_DIR="$HOME/Whisper-WebUI"
export OUTDIR="/path/to/transcript/output"
export PORT=7860

if [ ! -d "$CLONE_DIR/.git" ]; then
  git clone --depth 1 https://github.com/jhj0517/Whisper-WebUI.git "$CLONE_DIR"
fi
mkdir -p "$OUTDIR" "$CLONE_DIR/outputs" "$CLONE_DIR/models" "$CLONE_DIR/configs"

# Optional: export HF_TOKEN=… when using speaker diarization in the UI.
docker run --rm -d \
  --name whisper-webui \
  -p "127.0.0.1:${PORT}:7860" \
  -v "$CLONE_DIR/models:/Whisper-WebUI/models" \
  -v "$OUTDIR:/Whisper-WebUI/outputs" \
  -v "$CLONE_DIR/configs:/Whisper-WebUI/configs" \
  -e HF_TOKEN \
  jhj0517/whisper-webui:v1.0.8-4def223

# NVIDIA Linux hosts *may* add: --gpus all (not available as Metal on Docker Desktop Mac).
# Open http://127.0.0.1:$PORT
```

### Official upstream compose

Upstream also ships its own `docker-compose.yaml` (often with an NVIDIA `deploy` reservation and broader port publish). Prefer **this** recipe’s compose for TranscriptX hand-off defaults (localhost bind, pinned tag, no GPU assumption). If you use upstream compose instead, re-check port binding and GPU sections yourself — see [Whisper-WebUI README](https://github.com/jhj0517/Whisper-WebUI).

## Local install (no Docker)

Upstream ships `install.sh` / `install.bat` and `start-webui.sh` / `start-webui.bat` (Python 3.10–3.12, FFmpeg). See the [upstream README](https://github.com/jhj0517/Whisper-WebUI#run-locally). Pinokio is also supported upstream. Same ownership disclaimer applies: TranscriptX does not maintain that install path.

## Model cache and storage

- Host path: `$CLONE_DIR/models` (mounted at `/Whisper-WebUI/models`).
- Outputs: `$OUTDIR` (mounted at `/Whisper-WebUI/outputs`).
- **Storage warning:** Whisper weights and optional UVR/diarization assets are large. Expect **several GB** for a single large model; multiple models plus caches can reach **tens of GB**. Plan disk before first download. TranscriptX does not manage or prune this cache.

## Diarization / Hugging Face (your token)

Speaker diarization is optional and uses **gated** pyannote models. TranscriptX does **not** supply, store, or rotate Hugging Face tokens.

- You obtain and export `HF_TOKEN` on the host (or compose env).
- You accept upstream model terms before enabling diarization in the Gradio UI:
  1. [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
  2. [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
- Diarization quality is **not** promised to match TranscriptX’s preferred WhisperX JSON workflow.

## Expected output formats → Import Transcript

| WebUI export | Import Transcript |
|--------------|-------------------|
| `.srt` / `.vtt` | Supported — preferred path from this recipe |
| `.txt` (no timestamps) | Supported as text, but loses timing |
| WhisperX-style JSON | Not the default WebUI export; use the WhisperX recipe if you need that JSON |

Managed library admission still goes through **Import Transcript** (or `run_managed_import_workflow`) so canonical JSON + sidecar + archive are created — see [transcription.md](../../runtime/transcription.md) and the [Python import API](../../runtime/host-stt.md#python-api).

## Removal

```bash
# Compose (from this recipe directory)
docker compose -f docker-compose.whisper-webui.yml down

# Or docker run
docker stop whisper-webui   # --rm removes the container on stop

# Optional: delete host data you no longer need
# rm -rf "$CLONE_DIR"          # upstream clone + models/configs volumes
# rm -rf "$OUTDIR"             # exported SRT/VTT
# docker rmi jhj0517/whisper-webui:v1.0.8-4def223
```

TranscriptX library imports are **not** deleted by stopping the WebUI container. Remove library items separately in the app if desired.

## Ownership and support

This is an optional interoperability recipe for independently maintained third-party software. TranscriptX does not distribute, embed, fork or guarantee the Whisper service, its models, images, dependencies, output quality or hardware support. The recipe records a configuration that was manually verified on the stated date. Problems inside the transcription service should be reported upstream; TranscriptX accepts issues concerning only the documented hand-off and import behaviour.

TranscriptX consumes transcripts; it does not own transcription infrastructure. Upstream updates may break this recipe at any time — there is **no guarantee** that a newer image or commit remains compatible.

## Apple Silicon

**This container is expected to use CPU inference. Native MLX-based transcription may be substantially faster but is outside this recipe.**

On Mac, the container normally runs Whisper on the CPU, even on arm64. Docker documents generic Docker Desktop GPU access as Windows/WSL2-only, while these Whisper containers generally expose NVIDIA/CUDA acceleration. An M-series container therefore avoids Python dependency hell but does **not** gain native Metal acceleration. Prefer **whispermlx** / **whispermlx-missing** on the Mac host when speed matters; use this recipe when you want a local webpage that transcribes audio.

## Recipe identity

| Field | Value |
|-------|--------|
| Upstream repository | [jhj0517/Whisper-WebUI](https://github.com/jhj0517/Whisper-WebUI) |
| Upstream licence | [Apache License 2.0](https://github.com/jhj0517/Whisper-WebUI/blob/master/LICENSE) |
| Image tag documented here | `jhj0517/whisper-webui:v1.0.8-4def223` (Hub; also published as moving `latest`) |
| Upstream commit at recipe authoring | track via image tag / Hub digest — pin the tag above; do not rely on floating `latest` for reproducibility |
| Last manually verified | **pending** — recipe + `docker compose config` checked **2026-07-27**; full Gradio/import smoke not yet signed off |
| Expected exports | **SRT**, **WebVTT** (preferred); `.txt` (no timestamps) also possible |
| TranscriptX hand-off | **Import Transcript** for `.srt` / `.vtt` |
| Default bind | **localhost only** — `127.0.0.1:7860` (not `0.0.0.0`) |
| Model cache (host) | `$CLONE_DIR/models` → `/Whisper-WebUI/models` (often **multi‑GB**; large-v3 alone is several GB) |
| HF token | **Your** responsibility when enabling diarization (gated pyannote models) |

Update **Last manually verified** only after the [maintainer smoke checklist](#maintainer-smoke--release-obligation) below.

## Maintainer smoke / release obligation

Keep the TranscriptX release obligation deliberately tiny:

| Do | Do not |
|----|--------|
| Validate the example with `docker compose -f docker-compose.whisper-webui.yml config` | Pull Whisper models or run Whisper in normal CI |
| Manually smoke-test one short, redistributable audio fixture (maintainer machine) | Make upstream Hub/GitHub availability a TranscriptX release gate |
| Verify the documented export (`.srt` / `.vtt`) enters the supported Import Transcript path | Promise diarization equivalence with the preferred WhisperX workflow |
| Record image tag + **Last manually verified** date in the table above when smoke passes | Treat floating `latest` as a stable contract |

Product boundary: users get a useful escape hatch; TranscriptX still only owns hand-off docs and import behaviour.

## Boundaries

| Where | What runs |
|-------|-----------|
| Host Docker / Gradio | Whisper-WebUI transcription (third-party) |
| `transcriptx-web` | Import, library, analysis only |

Do not expect Streamlit to start or stop Whisper-WebUI. Analysis Docker and transcription Docker remain separate containers.
