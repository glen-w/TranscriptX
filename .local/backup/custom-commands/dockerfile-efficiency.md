# Dockerfile efficiency (# dockerfile-efficiency)

Assess and improve Docker image size and build hygiene for TranscriptX (main analysis image, UI image, optional WhisperX image) using a structured diagnosis and checklist. Do not change behavior; focus on size and hygiene.

Execute from the workspace root.

---

## 0. Run backup first (mandatory)

Before doing anything else, run the **backup** custom command (`# backup`). Wait for it to complete, then proceed with the steps below.

---

## 1. Quick diagnosis

- **`docker system df`** — see how much is images vs build cache vs volumes.
- **`docker images --digests`** — spot the real offenders.
- **`docker history <image>:<tag>`** — find the layer that adds the big chunk.
- Record a baseline (sizes, layer counts) before making changes.

---

## 2. Dockerfile hygiene

- **Base:** Use a small runtime base (e.g. `python:3.11-slim` or `debian:bookworm-slim`) for the analysis image.
- **Stages:** Keep build tools only in builder stage (gcc, make, rust, headers). In runtime stage, install only what you need (no compilers).
- **apt:** Add `--no-install-recommends` for apt installs. Always clean apt cache in the same layer: `rm -rf /var/lib/apt/lists/*`.
- **pip:** Use `pip install --no-cache-dir ...`. Do not copy a local venv into the image.
- **Current setup:** Note which Dockerfiles exist (e.g. `Dockerfile`, `Dockerfile.ui`). Document role of each; remove or update references to removed variants.

---

## 3. .dockerignore

- Ensure these are excluded: `.git/`, `.venv/`, `venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `dist/`, `build/`, `.ruff_cache/`.
- Exclude large local data folders: `outputs/`, `runs/`, `models/`, `tmp/` (or project equivalents).

---

## 4. Model / data strategy (biggest wins)

- Do not bake model weights into the image unless you truly must.
- Use a mounted volume for models/cache:
  - Hugging Face cache: `HF_HOME=/models/hf` (mounted).
  - Torch cache: `TORCH_HOME=/models/torch` (mounted).
- For WhisperX: prefer downloading Whisper/diarization models into a mounted `models/` volume, not into layers.

---

## 5. Layer / cache hygiene

- **Do not run prune.** Report that the following are disabled for safety after repeated data loss.
<!-- DISABLED: docker builder prune - commented out after repeated data loss. -->
<!-- DISABLED: docker image prune - commented out after repeated data loss. -->
<!-- DISABLED: docker system prune - commented out after repeated data loss. -->
- Check volumes (read-only): `docker volume ls` and `docker volume inspect` (HF caches often live here).
- Document when one would run prune so disk usage stays predictable (user may run manually if desired).

---

## 6. Implementation order

- Diagnosis → Dockerfile hygiene → .dockerignore → WhisperX (if maintained) → docs.

---

## Execution rules

- Do not change runtime behavior.
- After completion, summarize: baseline vs after, what was changed, and any remaining recommendations.
