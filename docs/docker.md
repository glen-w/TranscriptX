# Docker

**Docker Compose is the recommended way** to run TranscriptX in containers (no local Python required). The same CLI and Streamlit GUI run inside containers with mounted data. For an **interactive terminal** (menus, prompts), run the CLI service alone so it gets a real TTY; see Quickstart below.

TranscriptX is **analysis-only**; it does not run WhisperX or any transcription engine inside Docker. Bring your own transcript JSON (see [transcription.md](transcription.md) for how to generate compatible transcripts).

## Non-root /data write access

The default compose runs the `transcriptx` service as your host user (`user: "${UID:-1000}:${GID:-1000}"`) so that files written under the mounted `./data` volume are owned by you.

- **Dev / quick start:** If `/data` is not writable (e.g. permission denied), make the host directory writable: `chmod -R a+w data/` (or create `data` and then run compose).
- **Production:** Use the same `user: "${UID:-1000}:${GID:-1000}"` so the container runs as a known UID/GID; ensure the host `./data` (or your mount) is owned by that user or is group-writable as needed.

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
# Build amd64 image (required --load when building for a single platform with buildx)
docker buildx build --platform linux/amd64 --load -t transcriptx:amd64 .

# Run with same platform so the container matches the image
docker run --rm -v "$(pwd)/data:/data" --platform linux/amd64 transcriptx:amd64 analyze -t /data/transcripts/foo_transcriptx.json --modules stats --skip-confirm
```

Use `--platform linux/amd64` on **both** build and run when using the amd64 image on Apple Silicon. You can also run `docker compose build` to build using the default compose file.

### Primary commands: interactive CLI and GUI

From the repo root. For a **fully accessible terminal** (arrow keys, menus, same experience as the host CLI), use **`docker compose run -it --rm transcriptx`**. The **`-it`** flag allocates a pseudo-TTY and keeps stdin open; without it, the menu can disappear on the first arrow key. **`docker compose up transcriptx`** does not allocate a TTY—use **`run -it`** for the interactive menu.

**Interactive CLI (full terminal, recommended):**

```bash
docker compose run -it --rm transcriptx
```

Or explicitly: `docker compose run -it --rm transcriptx interactive`. Stop with Ctrl+C.

**If the menu disappears when you press arrow keys:** you're likely missing the TTY. Run with **`-it`**: `docker compose run -it --rm transcriptx`.

**Alternative (no full TTY):** `docker compose up transcriptx` runs the CLI in the foreground but without a TTY; arrow keys and menus may not work. Prefer `run -it` for interactive use.

**GUI:** Open http://localhost:8501 after starting the web service:

```bash
docker compose up transcriptx-web
```

**CLI and GUI together:** Start the GUI in the background, then the CLI with a full terminal in another terminal:

```bash
docker compose up -d transcriptx-web
docker compose run --rm transcriptx
```

**Other commands:**

- **CLI interactive menu (full terminal):** `docker compose run -it --rm transcriptx` or `docker compose run -it --rm transcriptx interactive`
- **One-off analysis (no menu):** `docker compose run --rm transcriptx analyze -t /data/transcripts/foo_transcriptx.json --modules stats --skip-confirm`
- **GUI only:** `docker compose up transcriptx-web`
- **Speaker Studio (instant playback, port 8502):** `docker compose up transcriptx-studio` → http://localhost:8502

### Operational modes

| Mode | Command |
|------|---------|
| **Interactive CLI** | `docker compose run -it --rm transcriptx` — full terminal (arrow keys, etc.) |
| **CLI one-off** | `docker compose run --rm transcriptx analyze ...` etc. |
| **GUI only** | `docker compose up transcriptx-web` |
| **Speaker Studio** | `docker compose up transcriptx-studio` — http://localhost:8502 (instant playback, speaker ID in browser) |
| **CLI + GUI** | `docker compose up -d transcriptx-web` then `docker compose run -it --rm transcriptx` |

### Without Compose

To run the image without Compose: `docker run -it --rm -v "$(pwd)/data:/data" transcriptx:latest` (interactive menu; `-it` required for arrow keys). or `docker run --rm -v "$(pwd)/data:/data" transcriptx:latest analyze -t /data/transcripts/foo_transcriptx.json --modules stats --skip-confirm`.

---

## Container I/O contract

The following layout is the formal contract for `TRANSCRIPTX_DATA_DIR` (e.g. `/data` in Docker). All paths are relative to that root.

```
/data/                              # TRANSCRIPTX_DATA_DIR
├── transcripts/                    # Input transcript JSONs
│   └── *.json | *_transcriptx.json
├── recordings/                     # Audio files (for playback/clips)
├── outputs/                        # All analysis outputs (TRANSCRIPTX_OUTPUT_DIR)
│   ├── <slug>/
│   │   └── <run_id>/               # YYYYMMDD_HHMMSS_<hash>
│   │       ├── manifest.json       # Artifact manifest (manifest_type: "artifact_manifest")
│   │       ├── run_results.json    # Run summary (schema_version: 1)
│   │       ├── .transcriptx/
│   │       │   └── manifest.json   # Run manifest (manifest_type: "run_manifest")
│   │       └── <module>/
│   │           ├── data/global/
│   │           ├── data/speakers/
│   │           └── charts/...
│   └── groups/                     # Group analysis outputs
├── cache/                          # Clip cache, model cache
│   └── clips/
├── playback-clips/                 # Exported clips for host playback
├── profiles/                        # Speaker profiles
└── transcriptx_data/               # SQLite DB and related data
    └── transcriptx.db              # Canonical DB (when TRANSCRIPTX_DATA_DIR=/data → /data/transcriptx_data/transcriptx.db)
```

The SQLite database is always `transcriptx_data/transcriptx.db` under `TRANSCRIPTX_DATA_DIR` (e.g. `/data/transcriptx_data/transcriptx.db` when `TRANSCRIPTX_DATA_DIR=/data`). Override with `TRANSCRIPTX_DATABASE_URL` if needed.

Consumers must load manifest files via the typed helpers (`load_artifact_manifest` / `load_run_manifest`) so the correct manifest type is used; see `src/transcriptx/core/pipeline/manifest_loader.py`.

---

## Volume layout

| Host path             | Container path (example) | Purpose                    |
|----------------------|---------------------------|----------------------------|
| `./data/transcripts` | `/data/transcripts`       | Transcript JSONs (in/out)  |
| `./data/outputs`     | `/data/outputs`           | Analysis run artifacts     |

Mount a single parent (e.g. `./data:/data`) so the CLI sees `/data/transcripts`, `/data/outputs`, etc.

The image sets **`TRANSCRIPTX_CONFIG_DIR=/data/.transcriptx`**, so the default config path in the container is `/data/.transcriptx/config.json`. When you mount `./data` at `/data`, saved config persists across container runs. Outside the container, the default is `<project>/.transcriptx/config.json`; override with `TRANSCRIPTX_CONFIG_DIR=/somewhere` to use `/somewhere/config.json`.

---

## Canonical transcript filename

Analysis expects **canonical** transcript files so that raw tool output is not analyzed by mistake.

- **Canonical:** filenames ending with `*_transcriptx.json` (e.g. `meeting1_transcriptx.json`).
- **Migration alias:** `*_canonical.json` is accepted for backward compatibility but is not the documented convention; use `*_transcriptx.json` for new files.

If you point the CLI at a file that does **not** look canonical (e.g. `foo.json`, `bar_whisperx.json`), TranscriptX will refuse to analyze it unless you pass **`--accept-noncanonical`** to the analyze command (use only when you know the file is safe to analyze).

All examples in this doc use the canonical name (e.g. `foo_transcriptx.json`).

> **Note:** Inside the container, paths start with `/data/...` (the mount point). On the host, the same files are under `./data/...` (relative to repo root).

---

## Speaker names and analysis

Most analysis modules require **named speakers** (e.g., "Alice", "Bob"). Raw WhisperX output uses system IDs (`SPEAKER_00`, `SPEAKER_01`) which are not considered named.

Before analysis, either:

1. Name your speakers: `docker compose run -it --rm transcriptx identify-speakers -t /data/transcripts/your_transcriptx.json`
2. Or pass `--skip-speaker-identification` to analyze with system IDs (modules needing named speakers will be skipped, but basic modules may still run).

Use a transcript with at least one human-named speaker to get full analysis output.

---

## Audio playback in Docker

**CLI speaker identification in Docker is export-only by design** on macOS and Windows: container audio is not reliably available cross-platform. For **instant playback** (hear a segment immediately in the browser), use **Speaker Studio** (web): run the `transcriptx-studio` service and open Speaker Studio in your browser; see [Speaker Studio](#speaker-studio-for-docker) below.

Containers usually have no display or sound device, so in-app playback (e.g. during **Identify Speakers** in the CLI) may not produce sound. Two options:

### 1. Export segments and play on the host (default)

When **`TRANSCRIPTX_PLAYBACK_EXPORT_DIR`** is set, each segment you “play” is also written as a WAV file in that directory. The Compose default is **`/data/playback-clips`**, which is inside the mounted `./data` volume, so files appear on the host at **`./data/playback-clips/`**.

1. Run speaker ID as usual: `docker compose run -it --rm transcriptx identify-speakers -t /data/transcripts/your_transcriptx.json`
2. Press **Space** (or your playback key) on a line. The UI will show e.g. **Segment exported to … (play on host or use Speaker Studio)**.
3. On the host, play the latest WAV:  
   `ffplay ./data/playback-clips/<filename>.wav`  
   or open `./data/playback-clips/` in your media player.

Override the directory: set `TRANSCRIPTX_PLAYBACK_EXPORT_DIR` in your environment or `.env` (e.g. to another path under `/data`).

### 2. Real playback with PulseAudio (optional)

If your host runs PulseAudio, you can forward audio into the container so ffplay plays through your speakers:

- **Linux host:** Share the Pulse socket and set `PULSE_SERVER`:
  ```bash
  docker compose run -it --rm \
    -v /run/user/$(id -u)/pulse:/run/user/$(id -u)/pulse \
    -e PULSE_SERVER=unix:/run/user/$(id -u)/pulse/native \
    transcriptx
  ```
  Then run **Identify Speakers** as usual; playback may work inside the container.

- **macOS/Windows:** Use a PulseAudio-compatible setup (e.g. PulseAudio on WSL or a network Pulse server) if you need in-container playback; otherwise use the export-dir method above.

### 3. Speaker Studio for Docker (recommended for speaker identification)

For **speaker identification** when using Docker on macOS or Windows, the recommended path is **Speaker Studio**: a browser-based flow where you click Play on a segment and hear it immediately (host browser audio). No export-dir step, no Pulse setup.

- Run the Speaker Studio service: `docker compose up transcriptx-studio` (port 8502).
- Open http://localhost:8502 and go to **Speaker Studio**.
- Select a transcript, click Play on a segment; audio plays in the browser. Assign speaker names; mapping is written back to the transcript JSON.

The CLI Identify Speakers flow remains available (export-only in Docker); use it for local runs or when you prefer the terminal.

---

## ENTRYPOINT and run contract

The transcriptx image uses **`ENTRYPOINT ["transcriptx"]`**. So:

- **Correct:** `docker run ... transcriptx:latest analyze ...`
- **Wrong:** `docker run ... transcriptx:latest transcriptx analyze ...` (double `transcriptx`).

Compose uses the same contract: `command: ["analyze", "-t", "/data/transcripts/foo_transcriptx.json", ...]` (no leading `transcriptx` in the command list).

---

## Downloads and cache

- **TRANSCRIPTX_DISABLE_DOWNLOADS**: In Docker Compose the default is **0** (allow downloads) so models can be cached in the `transcriptx_cache` volume. Set to **1** for offline or deterministic runs (see **Offline mode** below). Use this for reproducible, offline-safe runs. spaCy model auto-download is controlled separately by **TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD=1** (disable) or unset (allow by default when not in core mode).
- If you **enable** downloads (`TRANSCRIPTX_DISABLE_DOWNLOADS=0`), **mount cache volumes** or you will re-download on every run. Typical env vars and paths:
  - **Hugging Face:** `HF_HOME` (e.g. `~/.cache/huggingface`)
  - **TranscriptX cache:** `TRANSCRIPTX_CACHE_DIR`
  - **NLTK:** `NLTK_DATA`
  - **Matplotlib:** `MPLCONFIGDIR` (font cache)

When downloads are disabled and a required model is missing, the CLI fails fast with a message that tells you which volume or env to set.

**Offline mode:** To run without any runtime downloads (e.g. air-gapped or reproducible CI), set in your `.env` or environment: `TRANSCRIPTX_DISABLE_DOWNLOADS=1`. The image includes spaCy and NLTK data; HF models will not be downloaded.

---

## Permissions (Linux): writable /data

The default compose uses `user: "${UID:-1000}:${GID:-1000}"` so the container runs as your user and files under `./data` are owned by you. If you previously ran as root and outputs are root-owned, fix ownership once:

```bash
docker run --rm -v "$(pwd)/data/outputs:/data/outputs" transcriptx:latest chown -R "$(id -u):$(id -g)" /data/outputs
```

---

## Image labels (reproducibility)

Published images include OCI labels for debugging and support:

- `org.opencontainers.image.revision` — git commit SHA
- `org.opencontainers.image.version` — package version
- `org.opencontainers.image.created` — build date (ISO 8601)

To inspect:

```bash
docker inspect transcriptx:latest --format '{{json .Config.Labels}}'
```

---

## Docker efficiency baseline

To assess image size and find the layers that add the most, run (with the Docker daemon running):

- **Disk usage:** `docker system df` — images vs build cache vs volumes.
- **Image sizes:** `docker images --digests` — identify largest images.
- **Per-image layers:** `docker history transcriptx:latest` — find the layer with the largest SIZE.

See **[docker-efficiency-baseline.md](docker-efficiency-baseline.md)** for full commands and how to record your baseline.

---

## Docker maintenance (layer and cache hygiene)

If disk usage grows after many rebuilds, use:

- **Build cache:** `docker builder prune` — frees build cache.
- **Dangling layers:** `docker image prune` — removes dangling image layers.
- **Aggressive cleanup:** `docker system prune` — use only when you are sure (removes more).

---

## Core mode (runtime restriction)

The image is built with **full dependencies**. Core mode is a **runtime restriction** (env `TRANSCRIPTX_CORE=1` or CLI `--core`): it hides optional modules and blocks auto-install; it does not reduce image size.

---

## Pitfalls to avoid

1. **Constraints not enforced** — The image is built with `pip install -c constraints.txt -r requirements.txt` in the **builder stage only**. Do not add pip installs in the runtime stage or without `-c constraints.txt` in the builder, or CI/local dependency drift will only reproduce inside Docker.

2. **Missing runtime libs** — The runtime image includes **ffmpeg**, **libsndfile1**, **libgomp1**, and **ca-certificates** (soundfile/opensmile, audio handling, OpenMP). If you change the base image or strip packages, restore these or audio/NLP features may fail at runtime.

3. **Hidden writes in the GUI container** — The transcriptx-web service runs with `read_only: true` at the filesystem level. Besides `HOME=/tmp/streamlit_home` and tmpfs, the compose file sets **MPLCONFIGDIR**, **HF_HOME**, **TRANSCRIPTX_CACHE_DIR**, and **NLTK_DATA** to `/tmp/...` so Streamlit, matplotlib, Hugging Face, and NLTK do not write to default locations. Keep these env vars when changing the web service.

4. **Apple Silicon platform mismatch** — If you build for amd64 (`--platform linux/amd64`), you must **run** with the same platform (`docker run --platform linux/amd64 ...`) or you get exec format / ELF errors. Use `--platform linux/amd64` on **both** build and run when using the amd64 image on Apple Silicon.

5. **ENTRYPOINT contract drift** — The image uses `ENTRYPOINT ["transcriptx"]`. The correct form is `docker run ... analyze ...` and **not** `docker run ... transcriptx analyze ...`. Keep docs, compose examples, and CI smoke tests using the same contract (subcommand and args only, no leading `transcriptx` in the command).

6. **Can't move around menu / no arrow keys** — Use **`docker compose run -it --rm transcriptx`** (with **`-it`**). Without `-it`, Docker does not allocate a pseudo-TTY and the menu can disappear on the first arrow key. No image rebuild required.
