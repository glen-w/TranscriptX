# TranscriptX Dockerfile
# Multi-stage, wheel-based build. Builder uses constraints.txt; runtime has no pip.

# -----------------------------------------------------------------------------
# Builder: install deps with constraints, build wheel, install into venv
# -----------------------------------------------------------------------------
FROM python:3.10-slim AS builder

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
# Large wheels (torch, spacy models) can exceed pip's default 15s read timeout.
ENV PIP_DEFAULT_TIMEOUT=600
# Retry transient network failures; builder cache mount survives partial downloads.
ENV PIP_RETRIES=15
ENV PIP_CACHE_DIR=/root/.cache/pip

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

# Install dependencies only (constraints enforced); cache pip for faster rebuilds.
# TRANSCRIPTX_TORCH_VARIANT: default = PyPI torch (CUDA wheels on arm64); cpu = CPU-only PyTorch index.
ARG TRANSCRIPTX_TORCH_VARIANT=default
COPY constraints.txt requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    set -e; \
    pip_retry() { \
      attempt=1; \
      while [ "$attempt" -le 5 ]; do \
        if pip "$@"; then return 0; fi; \
        echo "pip failed (attempt ${attempt}/5), purging cache and retrying in ${attempt}0s..."; \
        pip cache purge 2>/dev/null || true; \
        sleep $((attempt * 10)); \
        attempt=$((attempt + 1)); \
      done; \
      return 1; \
    }; \
    pip_retry install -c constraints.txt "numpy==1.26.4"; \
    if [ "$TRANSCRIPTX_TORCH_VARIANT" = "cpu" ]; then \
      pip_retry install --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple \
        "numpy==1.26.4" "torch>=2.6.0" "torchvision>=0.15.0" "torchaudio>=2.2.0"; \
    fi; \
    pip_retry install -c constraints.txt -r requirements.txt

# Install build tool and build wheel
RUN --mount=type=cache,target=/root/.cache/pip pip install build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m build

# Install the application wheel into the venv (no editable install)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -c constraints.txt dist/*.whl

# Download spaCy language models so NLP modules work out of the box.
# lg is used by the documented higher-accuracy preset (TRANSCRIPTX_SPACY_MODEL=en_core_web_lg);
# runtime download fails in compose because /opt/venv is root-owned and the service runs as host UID.
RUN python -m spacy download en_core_web_md \
    && python -m spacy download en_core_web_sm \
    && python -m spacy download en_core_web_lg

# Pre-download NLTK data for sentiment/understandability modules
RUN python -c "\
import nltk; \
nltk.download('vader_lexicon', download_dir='/opt/venv/nltk_data'); \
nltk.download('punkt', download_dir='/opt/venv/nltk_data'); \
nltk.download('punkt_tab', download_dir='/opt/venv/nltk_data'); \
nltk.download('cmudict', download_dir='/opt/venv/nltk_data')"

# Pre-download TextBlob corpora for emotion module (NRCLex)
RUN python -m textblob.download_corpora

# -----------------------------------------------------------------------------
# Runtime: copy venv only; no pip, no build tools
# -----------------------------------------------------------------------------
FROM python:3.10-slim AS production

# Build-time args for OCI labels (set by CI or build script)
ARG GIT_SHA=
ARG TRANSCRIPTX_VERSION=
ARG BUILD_DATE=

# Runtime OS libs: soundfile/opensmile, ffmpeg/audio, OpenMP (tokenizers/vector libs),
# plus Playwright browser system dependencies for headless browser tasks.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libgomp1 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libdrm2 \
    libx11-6 \
    libxcb1 \
    libxext6 \
    libxrender1 \
    libglib2.0-0 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder (no pip in this stage)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# Numba (librosa): provide a writable cache dir so JIT can resolve a locator when site-packages
# is not writable and HOME may be unset/wrong under docker compose user: UID:GID overrides.
ENV NUMBA_CACHE_DIR=/data/.cache/numba
ENV NUMBA_DISABLE_CACHING=1
ENV NLTK_DATA=/opt/venv/nltk_data

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

# ENTRYPOINT: starts the Streamlit web interface.
# Default host: 0.0.0.0 so the port is reachable from outside the container.
# Override with --host / --port as needed.
ENTRYPOINT ["transcriptx"]
CMD ["--host", "0.0.0.0"]
