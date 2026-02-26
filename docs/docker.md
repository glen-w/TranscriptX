# Docker

**Docker Compose is the recommended way** to run TranscriptX in containers (no local Python required). The same CLI and Streamlit viewer run inside containers with mounted data. The default [docker-compose.yml](../docker-compose.yml) is the primary install route: `docker compose up` starts the CLI (foreground), WhisperX, and the web viewer.

**Security (trust boundary):** The default Compose setup mounts the Docker socket so the CLI can orchestrate WhisperX. Mounting the Docker socket gives the container **effective root equivalence on the host**. Only use this setup on machines you trust (including Docker Desktop on Mac/Windows).

## Quickstart

### Build

```bash
docker build -t transcriptx:latest .
```

Multi-arch (e.g. for publishing):

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t transcriptx:latest .
```

**Apple Silicon (M1/M2/M3):** If the arm64 build fails or you want maximum compatibility with CPU/torch wheels, build and run the amd64 image under emulation:

```bash
# Build amd64 image (required --load when building for a single platform with buildx)
docker buildx build --platform linux/amd64 --load -t transcriptx:amd64 .

# Run with same platform so the container matches the image
docker run --rm -v "$(pwd)/data:/data" --platform linux/amd64 transcriptx:amd64 analyze -t /data/transcripts/foo_transcriptx.json --modules stats --skip-confirm
```

Use `--platform linux/amd64` on **both** build and run when using the amd64 image on Apple Silicon. You can also run `docker compose build` to build using the default compose file.

### Primary command: run everything

From the repo root:

```bash
docker compose up
```

This starts the transcriptx service (interactive CLI) in the foreground, and whisperx and transcriptx-web in the background. Open http://localhost:8501 for the web viewer. Stop with Ctrl+C in that terminal, or run `docker compose down`.

- **Run only the CLI** (e.g. when services are already up; Docker socket is mounted by default): `docker compose run --rm -it transcriptx interactive`
- **One-off analysis:** `docker compose run --rm transcriptx analyze -t /data/transcripts/foo_transcriptx.json --modules stats --skip-confirm`
- **Viewer only:** `docker compose up transcriptx-web` (no profile; still uses the default compose file)

### Operational modes

| Mode | Command |
|------|---------|
| **All-in-one (recommended)** | `docker compose up` — CLI + WhisperX + viewer |
| **CLI one-off** | `docker compose run --rm transcriptx analyze ...` |
| **Viewer only** | `docker compose up transcriptx-web` |

### WhisperX (transcription)

WhisperX is included in the default `docker compose up` (whisperx service). The CLI container has the Docker socket mounted and can drive WhisperX via `docker exec`. **WhisperX runs on CPU by default and may be slow on long audio.** GPU is optional and requires additional Docker host setup (e.g. nvidia-container-toolkit).

Transcription output must be normalized to TranscriptX's canonical schema and named with the **canonical filename** (see below) before running analysis.


---

#### Using WhisperX when running the CLI in Docker

With the **default compose file**, the transcriptx service already has the Docker socket mounted and whisperx starts with `docker compose up`, so the CLI can use WhisperX immediately—no extra steps.

The default `docker-compose.yml` mounts the Docker socket, so `docker compose run --rm -it transcriptx interactive` (or `docker compose up`) gives you WhisperX support without extra flags. If you run the CLI via plain `docker run` (without Compose), mount the socket and start WhisperX from the host: `docker compose -f docker-compose.whisperx.yml --profile whisperx up -d whisperx`, then `docker run -it --rm -v "$(pwd)/data:/data" -v /var/run/docker.sock:/var/run/docker.sock transcriptx:latest`.

### Without Compose

To run the image without Compose: `docker run -it --rm -v "$(pwd)/data:/data" transcriptx:latest` (interactive menu) or `docker run --rm -v "$(pwd)/data:/data" transcriptx:latest analyze -t /data/transcripts/foo_transcriptx.json --modules stats --skip-confirm`. For WhisperX you must also mount the Docker socket and start the WhisperX stack from the host (see above). The primary path is the default compose file.

---

## Volume layout

| Host path             | Container path (example) | Purpose                          |
|----------------------|---------------------------|----------------------------------|
| `./data/recordings`   | `/data/recordings`        | Input audio for WhisperX (optional) |
| `./data/transcripts` | `/data/transcripts`       | Transcript JSONs (in/out)         |
| `./data/outputs`     | `/data/outputs`          | Analysis run artifacts           |

Mount a single parent (e.g. `./data:/data`) so the CLI sees `/data/transcripts`, `/data/outputs`, etc.

The image sets **`TRANSCRIPTX_CONFIG_DIR=/data/.transcriptx`**, so the default config path in the container is `/data/.transcriptx/config.json`. When you mount `./data` at `/data`, saved config persists across container runs. Outside the container, the default is `<project>/.transcriptx/config.json`; override with `TRANSCRIPTX_CONFIG_DIR=/somewhere` to use `/somewhere/config.json`.

---

## Canonical transcript filename

Analysis expects **canonical** transcript files so that raw WhisperX (or other) output is not analyzed by mistake.

- **Canonical:** filenames ending with `*_transcriptx.json` (e.g. `meeting1_transcriptx.json`).
- **Migration alias:** `*_canonical.json` is accepted for backward compatibility but is not the documented convention; use `*_transcriptx.json` for new files.

If you point the CLI at a file that does **not** look canonical (e.g. `foo.json`, `bar_whisperx.json`), TranscriptX will refuse to analyze it unless you pass **`--accept-noncanonical`** to the analyze command (use only when you know the file is safe to analyze).

All examples in this doc use the canonical name (e.g. `foo_transcriptx.json`).

---

## ENTRYPOINT and run contract

The transcriptx image uses **`ENTRYPOINT ["transcriptx"]`**. So:

- **Correct:** `docker run ... transcriptx:latest analyze ...`  
- **Wrong:** `docker run ... transcriptx:latest transcriptx analyze ...` (double `transcriptx`).

Compose uses the same contract: `command: ["analyze", "-t", "/data/transcripts/foo_transcriptx.json", ...]` (no leading `transcriptx` in the command list).

---

## Downloads and cache

- **TRANSCRIPTX_DISABLE_DOWNLOADS=1** (default in CI and many setups) disables model/data downloads. Use this for reproducible, offline-safe runs. spaCy model auto-download is controlled separately by **TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD=1** (disable) or unset (allow by default when not in core mode).
- If you **enable** downloads (`TRANSCRIPTX_DISABLE_DOWNLOADS=0`), **mount cache volumes** or you will re-download on every run. Typical env vars and paths:
  - **Hugging Face:** `HF_HOME` (e.g. `~/.cache/huggingface`)
  - **TranscriptX cache:** `TRANSCRIPTX_CACHE_DIR`
  - **NLTK:** `NLTK_DATA`
  - **Matplotlib:** `MPLCONFIGDIR` (font cache)

When downloads are disabled and a required model is missing, the CLI fails fast with a message that tells you which volume or env to set (e.g. mount a cache volume or set `TRANSCRIPTX_DISABLE_DOWNLOADS=0` and run once to populate the cache).

---

## Hugging Face token via Docker secrets

You can provide the Hugging Face token via a **file-based secret** instead of env vars, so the token is not in `.env` or process listings.

1. **Create the secret file:** Put your token in `./secrets/hf_token` (token only, no newline). For example:
   ```bash
   mkdir -p secrets && echo -n 'YOUR_TOKEN' > secrets/hf_token && chmod 600 secrets/hf_token
   ```
   Or use **`make secrets-hf`** to be prompted and have the file created with safe permissions.
2. **Run with the secrets override:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.secrets.yml up
   ```
   Or **`make up-secrets`**. The override mounts the secret and sets `TRANSCRIPTX_HUGGINGFACE_TOKEN_FILE=/run/secrets/hf_token` so the app reads the token from the file.
3. **Do not commit the file:** `secrets/` is in `.gitignore`; keep it that way.

Without the override, env-based token still works: set `TRANSCRIPTX_HUGGINGFACE_TOKEN` or `HF_TOKEN` in `.env` or your environment. The same override can be used with other stacks (e.g. `-f docker-compose.whisperx.yml -f docker-compose.secrets.yml`); the secret name `hf_token` is the same everywhere.

**Threat model:** File-based secrets protect against accidental git commit and casual inspection. Anyone with Docker access on the host can still read the secret (e.g. via `docker exec` or inspect). Do not paste tokens into terminal history; use an editor or `cat > secrets/hf_token` when creating the file.

---

## Permissions (Linux): root-owned outputs

On Linux hosts, files written by the container under mounted volumes are often owned by root. Two options:

**Option 1 (recommended):** Run the container as your user so outputs match the host:

In `docker-compose.yml` for the `transcriptx` (and optionally `whisperx`) service:

```yaml
user: "${UID:-1000}:${GID:-1000}"
```

**Option 2:** If you already ran as root and outputs are root-owned, fix ownership once:

```bash
docker run --rm -v "$(pwd)/data/outputs:/data/outputs" transcriptx:latest chown -R "$(id -u):$(id -g)" /data/outputs
```

**Warning:** Running the container as root in production is not recommended; use this only as a one-time recovery.

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

Record the one or two layers that dominate size so you can compare before/after changes. See **[docker-efficiency-baseline.md](docker-efficiency-baseline.md)** for full commands and how to record your baseline.

**Model strategy:** Do not bake Whisper / Hugging Face / diarization models into images. Use the mounted volume (or equivalent) for WhisperX. The default compose uses the external WhisperX image and the `whisperx_hf_cache` named volume for `/root/.cache/huggingface`. If you build and run the custom **Dockerfile.whisperx** image, set **HF_HOME** and **TORCH_HOME** at runtime to a mounted path (e.g. a named volume or host directory) so model caches live off the image; see the comments in that Dockerfile.

---

## Docker maintenance (layer and cache hygiene)

If disk usage grows after many rebuilds, use:

- **Build cache:** `docker builder prune` — frees build cache.
- **Dangling layers:** `docker image prune` — removes dangling image layers.
- **Aggressive cleanup:** `docker system prune` — use only when you are sure (removes more).

To see where space is used by volumes (e.g. Hugging Face cache): `docker volume ls` and `docker volume inspect <name>`. The default compose uses the named volume `whisperx_hf_cache` for the WhisperX Hugging Face cache; it persists across container runs and can grow large.

---

## Core mode (runtime restriction)

The image is built with **full dependencies**. Core mode is a **runtime restriction** (env `TRANSCRIPTX_CORE=1` or CLI `--core`): it hides optional modules and blocks auto-install; it does not reduce image size.

---

## Pitfalls to avoid

These safeguards keep the Docker setup reproducible and prevent "works locally, fails in container" regressions.

1. **Constraints not enforced** — The image is built with `pip install -c constraints.txt -r requirements.txt` in the **builder stage only**. Do not add pip installs in the runtime stage or without `-c constraints.txt` in the builder, or CI/local dependency drift will only reproduce inside Docker.

2. **Missing runtime libs** — The runtime image includes **ffmpeg**, **libsndfile1**, **libgomp1**, and **ca-certificates** (soundfile/opensmile, audio handling, OpenMP). If you change the base image or strip packages, restore these or audio/NLP features may fail at runtime.

3. **Hidden writes in the viewer** — The transcriptx-web service runs with `read_only: true`. Besides `HOME=/tmp/streamlit_home` and tmpfs, the compose file sets **MPLCONFIGDIR**, **HF_HOME**, **TRANSCRIPTX_CACHE_DIR**, and **NLTK_DATA** to `/tmp/...` so Streamlit, matplotlib, Hugging Face, and NLTK do not write to default locations. Keep these env vars when changing the viewer service.

4. **Apple Silicon platform mismatch** — If you build for amd64 (`--platform linux/amd64`), you must **run** with the same platform (`docker run --platform linux/amd64 ...`) or you get exec format / ELF errors. Use `--platform linux/amd64` on **both** build and run when using the amd64 image on Apple Silicon.

5. **ENTRYPOINT contract drift** — The image uses `ENTRYPOINT ["transcriptx"]`. The correct form is `docker run ... analyze ...` and **not** `docker run ... transcriptx analyze ...`. Keep docs, compose examples, and CI smoke tests using the same contract (subcommand and args only, no leading `transcriptx` in the command).
