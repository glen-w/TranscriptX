# Docker Rebuild & Launch (# rebuild)

Full rebuild of the TranscriptX Docker setup: tear down, prune, build images, then start services with docker compose.

Execute from the workspace root. Use when you want a clean rebuild (e.g. after dependency or Dockerfile changes).

---

## 1. Tear down

- **Stop and remove containers, networks (keep volumes)**  
  `docker compose down`

---

## 2. Prune

- **Prune build cache**  
  `docker builder prune -f`
- **Prune dangling images**  
  `docker image prune -f`

(Optional: for aggressive cleanup use `docker system prune -f`; this also prunes unused networks and stopped containers.)

---

## 3. Build

- **Build images (no cache)**  
  `docker compose build --no-cache`

This rebuilds the main `transcriptx:latest` image used by the `transcriptx` and `transcriptx-web` services. The `whisperx` service uses an external image and is not rebuilt.

---

## 4. Launch

- **Interactive CLI**  
  `docker compose run --rm transcriptx interactive`

To run services in the background instead:  
`docker compose up -d`

---

## Execution rules

- Run all steps in order from the project root.
- Use the default compose file: `docker-compose.yml`.
- After completion, confirm: containers down → prune → build succeeded → services started; list running containers with `docker compose ps` if useful.
