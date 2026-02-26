# Dockerfile Efficiency Assessment (# dockerfile-efficiency)

Assess and improve Docker image size and build hygiene for TranscriptX (main analysis image, UI image, optional WhisperX image) using a structured diagnosis and checklist. Do not change runtime behavior.

Execute from the workspace root. After running, summarize findings, baseline (if captured), and any changes made.

---

## Current setup (reference)

| Image              | File                | Role                                                                   |
| ------------------ | ------------------- | ---------------------------------------------------------------------- |
| transcriptx:latest | Dockerfile          | CLI + analysis + web viewer (multi-stage, wheel-based)                  |
| (UI variant)       | Dockerfile.ui       | Gradio UI; single-stage, full copy + editable install                   |
| (custom WhisperX)  | Dockerfile.whisperx | Alternative WhisperX (compose default: ghcr.io/jim60105/whisperx + volume) |

Default runtime: docker-compose.yml — main image + external WhisperX + `whisperx_hf_cache` volume.

---

## 1. Quick diagnosis (baseline)

Run once and record results for before/after comparison:

- **Disk usage:** `docker system df` — images vs build cache vs volumes.
- **Image sizes:** `docker images --digests` — identify largest images (transcriptx, whisperx, UI).
- **Per-image layers:** `docker history <image>:<tag>` (e.g. `transcriptx:latest`) — find the layer that adds the most size (often a single `RUN pip install` or `apt-get`).
- Optional: build with `--progress=plain` and note layer sizes in the build log.

**Deliverable:** Short “Docker efficiency baseline” note (in docs or repo) with command outputs and the one or two layers that dominate size for each image you care about.

---

## 2. Dockerfile hygiene (per file)

### 2.1 Main image — Dockerfile

Check (already expected to be in good shape):

- Small runtime base: `python:3.10-slim` (or 3.11 if standardized).
- Build tools only in builder stage; runtime stage has only ffmpeg, libsndfile1, libgomp1, ca-certificates, docker.io.
- apt: `--no-install-recommends` and `rm -rf /var/lib/apt/lists/*` in the same RUN (builder and runtime).
- Pip: `PIP_NO_CACHE_DIR=1` in builder; installs with `-c constraints.txt`; no venv copied; wheel built in builder, installed from dist in runtime.

**Possible tweaks:** Explicit `pip install --no-cache-dir` (or keep `PIP_NO_CACHE_DIR=1` only) for clarity; if moving to 3.11 elsewhere, switch both stages to `python:3.11-slim`.

### 2.2 UI image — Dockerfile.ui

Gaps to address:

- Single stage: build deps and runtime in same layer → image larger.
- apt: add `--no-install-recommends` and keep `rm -rf /var/lib/apt/lists/*` in the same RUN.
- Pip: use constraints.txt if available for UI extra; avoid editable install in final image when possible.
- Context: avoid `COPY . .` pulling in docs/tests (ensure .dockerignore is tight).

**Recommended:** Add `--no-install-recommends` and same-layer apt cleanup; prefer multi-stage build (builder + wheel, runtime with wheel only). If keeping single-stage: at least apt hygiene, constraints for UI, and tighten .dockerignore.

### 2.3 WhisperX image — Dockerfile.whisperx

Only if this image is maintained:

- Add `--no-install-recommends` and `rm -rf /var/lib/apt/lists/*` in the same RUN.
- Prefer multi-stage: builder for compile-time deps and pip install, runtime with only runtime libs (no build-essential in final).
- Document in comments or docs/docker.md: mount a volume for HF/Torch cache (e.g. HF_HOME, TORCH_HOME) so models are not stored in image layers.

---

## 3. Model / data strategy

- Do not bake Whisper/HF/diarization models into images; use mounted volume (or equivalent) for WhisperX.
- If maintaining Dockerfile.whisperx: add env vars (HF_HOME, TORCH_HOME) and document mounting a host/volume path.

---

## 4. .dockerignore

Ensure .dockerignore includes (add if missing):

- `.git/`, `.venv/`, `venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `dist/`, `build/`
- `data/`, `outputs/`, `runs/`, `models/`, `tmp/`
- `docs/`, `tests/`, `examples/`, `.github`, `.cursor`

---

## 5. Layer / cache hygiene (docs)

Document in docs/docker.md (or a “Docker maintenance” section) when to run:

- **Build cache:** `docker builder prune` — after many rebuilds.
- **Dangling images:** `docker image prune`.
- **Aggressive cleanup:** `docker system prune` — only when appropriate.
- **Volumes:** `docker volume ls` and `docker volume inspect` — document that HF/cache often live in named volumes (e.g. whisperx_hf_cache).

No Dockerfile code changes; docs-only for this step.

---

## Implementation order (suggested)

1. **Diagnosis:** Run `docker system df`, `docker images --digests`, `docker history` for transcriptx:latest (and optionally UI/WhisperX if built); record baseline.
2. **Low-risk hygiene:** Update Dockerfile.ui: add `--no-install-recommends`, same-layer `rm -rf /var/lib/apt/lists/*`; optionally use constraints and multi-stage when ready.
3. **.dockerignore:** Add `runs/`, `models/`, `tmp/` if relevant.
4. **Dockerfile.whisperx (if maintained):** Add apt hygiene, document model volume (HF_HOME/TORCH_HOME); consider multi-stage.
5. **Docs:** Add “Docker efficiency baseline” and “Layer/cache hygiene” (prune + volume inspection) to docs/docker.md.

---

## Execution rules

- Do not change runtime behavior of the application.
- Prefer small, low-risk hygiene changes unless explicitly asked for larger refactors (e.g. full multi-stage for UI).
- After completion, summarize:
  - Baseline (disk usage, image sizes, dominant layers) if captured.
  - Changes made (per Dockerfile and .dockerignore).
  - Doc updates.
  - Remaining recommendations (e.g. multi-stage UI, GPU WhisperX notes) if not implemented.
