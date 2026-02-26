# TranscriptX Dockerfile
# Multi-stage, wheel-based build. Builder uses constraints.txt; runtime has no pip.

# -----------------------------------------------------------------------------
# Builder: install deps with constraints, build wheel, install into venv
# -----------------------------------------------------------------------------
FROM python:3.10-slim AS builder

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps: libsndfile1-dev for soundfile/opensmile wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    git \
    curl \
    libffi-dev \
    libssl-dev \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create venv; all pip installs use -c constraints.txt (reproducible, no drift)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies only (constraints enforced)
COPY constraints.txt requirements.txt ./
RUN pip install -c constraints.txt -r requirements.txt

# Install build tool and build wheel
RUN pip install build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m build

# Install the application wheel into the venv (no editable install)
RUN pip install -c constraints.txt dist/*.whl

# -----------------------------------------------------------------------------
# Runtime: copy venv only; no pip, no build tools
# -----------------------------------------------------------------------------
FROM python:3.10-slim AS production

# Build-time args for OCI labels (set by CI or build script)
ARG GIT_SHA=
ARG TRANSCRIPTX_VERSION=
ARG BUILD_DATE=

# Runtime OS libs: soundfile/opensmile, ffmpeg/audio, OpenMP (tokenizers/vector libs), Docker CLI for WhisperX
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libgomp1 \
    ca-certificates \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder (no pip in this stage)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Data dir override so the app uses /data (mounted volume) instead of under site-packages
ENV TRANSCRIPTX_DATA_DIR=/data
# Config dir so default config save path is on the volume (e.g. /data/.transcriptx/config.json)
ENV TRANSCRIPTX_CONFIG_DIR=/data/.transcriptx

# Non-root user
RUN useradd --create-home --shell /bin/bash transcriptx
USER transcriptx

WORKDIR /data

# OCI labels for reproducibility
LABEL org.opencontainers.image.revision="${GIT_SHA}"
LABEL org.opencontainers.image.version="${TRANSCRIPTX_VERSION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"

# ENTRYPOINT contract: use "docker run ... analyze ..." (no extra "transcriptx" before subcommand)
# Default: interactive CLI menu; use -it for TTY. Override with e.g. --help or analyze ...
ENTRYPOINT ["transcriptx"]
CMD ["interactive"]
