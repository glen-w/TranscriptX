# Docker rebuild (# rebuild)

Tear down existing containers, prune Docker build cache and images, rebuild the image, then launch using docker compose.
Execute from the workspace root.

---

## 0. Run backup first (mandatory)

Before doing anything else, run the **backup** custom command (`# backup`). Wait for it to complete, then proceed with the steps below.

---

## 1. Tear down

<!-- DISABLED: docker compose down (removes containers) - commented out after repeated data loss. -->
- **Do not run `docker compose down`** unless the user explicitly requests it. Report that tear-down is disabled for safety.
<!-- - docker compose down - DISABLED -->

---

## 2. Prune

<!-- DISABLED: All docker prune (removes images/cache) - commented out after repeated data loss. -->
- **Do not run** `docker builder prune`, `docker image prune`, or `docker system prune`. Report that prune steps are disabled for safety.
<!-- - docker builder prune -f - DISABLED -->
<!-- - docker image prune -f - DISABLED -->
<!-- - docker system prune -f - DISABLED -->

---

## 3. Build

- **Rebuild the image (no cache):** `docker compose build --no-cache`
- This rebuilds the main TranscriptX image (e.g. `transcriptx:latest`). External service images (e.g. WhisperX) are pulled, not rebuilt, unless specified in docker-compose.

---

## 4. Launch

- **Web UI (recommended):** `docker compose up transcriptx-web` (or `docker compose up -d` for detached). Open http://localhost:8501 .
- **One-off smoke:** `docker compose run --rm -p 8501:8501 transcriptx-web --host 0.0.0.0` then hit `/_stcore/health`.

---

## Execution rules

- Run all steps from the workspace root where `docker-compose.yml` lives.
- After completion, confirm that the container starts and the entrypoint works (e.g. `docker compose run --rm transcriptx-web --help`).
