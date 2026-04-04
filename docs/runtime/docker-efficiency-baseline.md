# Docker efficiency baseline

Run these commands with the Docker daemon running to assess image size and find the layers that add the most. Record the output here (or in a local note) so you can compare before/after changes.

## Disk usage

```bash
docker system df
```

Shows: images, build cache, volumes (and optionally containers). Use this to see where space is used.

## Image sizes and digests

```bash
docker images --digests
```

Identifies the largest images (e.g. `transcriptx`, `whisperx`, UI variant). Focus on the ones you build locally.

## Per-image layer breakdown

Find the layer that adds the largest size (often a single `RUN pip install` or `apt-get`):

```bash
docker history transcriptx:latest
```

Optional, for UI or custom WhisperX images if you build them:

```bash
docker history transcriptx-ui:latest
docker history transcriptx-whisperx:latest
```

## Recording your baseline

After running the commands above, note:

1. **Largest images** — Image name and approximate size from `docker images`.
2. **Largest layer(s)** — From `docker history`, the one or two rows with the biggest SIZE column for `transcriptx:latest` (and others if relevant).

Example note:

- `transcriptx:latest`: total ~XXX MB; largest layer: RUN pip install ... (~YYY MB).
- Build cache / volumes: from `docker system df`.

Optional: build with `--progress=plain` to see layer sizes in the build log:

```bash
docker build --progress=plain -t transcriptx:latest . 2>&1 | tee build.log
```

---

## Recorded baseline (example)

As of a recent run (Docker daemon on macOS):

| Image                | Size   | Dominant layers |
|----------------------|--------|-----------------|
| transcriptx:latest   | 3.74GB | COPY /opt/venv → 2.12GB; apt-get (ffmpeg, libsndfile1, libgomp1, ca-certificates, docker.io) → 597MB |
| ghcr.io/.../whisperx (no_model) | 1.91GB | External image; not built from repo |

**Note:** `docker system df` may report snapshot errors on some Docker Desktop setups; use `docker images` and `docker history <image>` for per-image assessment.
