# STT stacks together (analysis + host whispermlx + optional WhisperX / WebUI)

TranscriptX analysis and speech-to-text are **separate processes**. There is no single Compose file that starts Whisper inside `transcriptx-web`. This page is the operator recipe for running the pieces **at the same time** and sharing folders so Import / Admit work.

**whispermlx must run on the macOS host.** It is a Metal/MLX binary. It cannot run in the Linux analysis image, and Docker Desktop on Mac cannot give it GPU.

Engines stay **out of** `transcriptx:latest`. The GUI can **orchestrate** them only when those binaries are visible to the Streamlit process. Canonical Compose does **not** mount `/var/run/docker.sock` and does **not** ship a `docker` CLI (analysis-only image).

Mainstream Transcribe Audio steps: [transcription.md](../../runtime/transcription.md). Bulk host scripts: [host-stt.md](../../runtime/host-stt.md).

## What runs where

| Piece | Process | Typical URL / command | Role |
|-------|---------|------------------------|------|
| TranscriptX GUI | `transcriptx-web` Compose **or** native `./transcriptx.sh` | http://127.0.0.1:8501 | Import, admit, analysis. **Run in app** only if providers are visible. |
| whispermlx | **macOS host** (`PATH` or `WHISPERMLX`) | `whispermlx …` / `whispermlx-missing` / `inbox-watch` | Preferred STT on Apple Silicon. |
| WhisperX | Host `docker run` (Copy command) | Transcribe Audio → Copy command | Diarized JSON when Docker is on the host. |
| Whisper-WebUI | Optional extra Compose service | http://127.0.0.1:7860 | Gradio UI → SRT/VTT → Import Transcript. |

Pick **one** Streamlit process for a given library (`TRANSCRIPTX_DATA_DIR` / `HOST_TRANSCRIPTS_DIR`). Do not run Compose GUI and native GUI against the same data dir at once.

## Shared folders (the wiring)

Use the **same host paths** in `.env`, `whisperx.env`, and host JSON configs. Do not point WhisperX’s recipe-local `./data/transcripts` at a clone-relative folder if your library lives elsewhere.

| Host path (examples) | Who writes | Who reads |
|----------------------|------------|-----------|
| `HOST_RECORDINGS_DIR` | recorder, `inbox-watch` convert, Tools → Merge | STT, playback, Compose `/mnt/recordings` |
| `HOST_TRANSCRIPTS_DIR/originals/` | whispermlx-missing, WhisperX JSON, host watchers | **Admit from originals/**, `inbox-watch --admit` |
| Managed library root (`HOST_TRANSCRIPTS_DIR`) | Import / Admit | analysis |
| `HOST_TRANSCRIPT_INBOX_DIR` | you drop BYO files | Import all from folder / in-app watcher — **not** `originals/` |
| `whisperx.env` (`HF_TOKEN`, `WHISPERMLX`) | you | host STT and Copy command env-file field |

`originals/` is not the import inbox. If STT succeeds but the library looks empty, admit from `originals/` — see ROADMAP **Now** (folder hygiene).

## Choose a topology

### A — Compose GUI + host whispermlx (recommended on this Mac)

Use when analysis should stay in Docker and STT should use Metal.

1. `.env` with `HOST_RECORDINGS_DIR` (absolute, outside the clone).
2. Analysis GUI:

   ```bash
   docker compose up -d transcriptx-web
   ```

3. Host STT (pick one):
   - USB / drop folder: `inbox-watch` with `--transcribe whispermlx-missing` and optional `--admit` — [host-stt.md](../../runtime/host-stt.md#host-inbox-watcher-inbox-watch)
   - Batch folder: `whispermlx-missing` writing JSON under `…/originals/`
   - One-off: Transcribe Audio → **Copy command** → **whispermlx** / **whispermlx-missing**, paste into a **host** terminal (not `docker exec` into `transcriptx-web`)

4. In the GUI: **Import Transcript** or **Admit from originals/**.

**Run in app** and watcher **`auto_transcribe` inside Compose** will usually show providers unavailable (no `whispermlx`, no `docker` CLI). That is expected. Use Copy command or host `inbox-watch`.

### B — Native GUI + host whispermlx (Run in app)

Use when you want Transcribe Audio → **Run in app** to call whispermlx itself.

1. `whispermlx` on `PATH`, or `WHISPERMLX` in repo-root `whisperx.env`.
2. `./transcriptx.sh` (or `python -m transcriptx.web`).
3. Transcribe Audio → **Run in app** → whispermlx.
4. Optional: same machine can still `docker run` WhisperX if Docker Desktop is up (**Run in app** → WhisperX Docker), because native Streamlit sees the host `docker` CLI.

Do not also `docker compose up transcriptx-web` against the same library.

### C — Compose GUI + WhisperX on the host

Use when you need CUDA WhisperX (Linux NVIDIA) or CPU WhisperX in Docker, with analysis still in Compose.

1. `docker compose up -d transcriptx-web`
2. Transcribe Audio → **Copy command** → **WhisperX Docker** → run the snippet **on the host**.
3. Point output at `HOST_TRANSCRIPTS_DIR/originals/` (or import the JSON file).
4. Full flags / `HF_TOKEN`: [WhisperX recipe](../whisperx/README.md)

The idle `docker-compose.whisperx.yml` service (`docker exec` into a long-running container) is a **standalone reference**. It is **not** what **Run in app** calls. Run in app uses `docker run --rm`.

### D — Optional Whisper-WebUI beside analysis Compose

Gradio is a third container. It does not speak to Streamlit except through files you import.

From the **repo root** (loads `.env`; keep local override if you use it):

```bash
export CLONE_DIR="${CLONE_DIR:-$HOME/Whisper-WebUI}"
export OUTDIR="${OUTDIR:-$HOME/whisper-webui-outputs}"
mkdir -p "$OUTDIR" "$CLONE_DIR/models" "$CLONE_DIR/outputs" "$CLONE_DIR/configs"

docker compose \
  -f docker-compose.yml \
  -f docker-compose.override.yml \
  -f docs/recipes/stt-stacks/docker-compose.stt-stacks.yml \
  up -d
```

Omit `-f docker-compose.override.yml` if that file is absent. Open http://127.0.0.1:8501 (analysis) and http://127.0.0.1:7860 (WebUI). Export **SRT/VTT** → Import Transcript. Details: [Whisper-WebUI recipe](../whisper-webui/README.md).

Validate without pulling images:

```bash
docker compose \
  -f docker-compose.yml \
  -f docs/recipes/stt-stacks/docker-compose.stt-stacks.yml \
  config
```

(`HOST_RECORDINGS_DIR` must be set in `.env` for the analysis service.)

## What this recipe will not do

- Put whispermlx inside `transcriptx-web`.
- Mount the Docker socket into the analysis container (forbidden by analysis-only invariants).
- Start Parakeet / Canary / YouTube (theme **H5+**, deferred).
- Auto-join meeting bots.

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Run in app: provider unavailable in Compose GUI | Expected. Use topology A Copy command / host watchers, or topology B native GUI. |
| whispermlx not found | Install on macOS host; `which whispermlx`; set `WHISPERMLX` in `whisperx.env`. |
| JSON on disk, empty library | Wrote `originals/` but did not Admit; or Import all from folder pointed at the wrong inbox. |
| WhisperX 403 / gated model | `HF_TOKEN` + accept pyannote terms — [WhisperX recipe](../whisperx/README.md#troubleshooting). |
| Two GUIs fighting | Stop Compose or native; one Streamlit per library. |
