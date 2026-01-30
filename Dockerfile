# TranscriptX Dockerfile
# Multi-stage build for optimal image size and security

# Stage 1: Base Python environment
FROM python:3.10-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libffi-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Stage 2: Development dependencies
FROM base AS development

# Copy requirements first for better caching
COPY requirements*.txt ./

# Install Python dependencies from requirements.txt for consistency
RUN pip install --no-cache-dir -r requirements.txt

# Install development dependencies
RUN pip install --no-cache-dir -r requirements-dev.txt

# Download spaCy models
RUN python -m spacy download en_core_web_sm

# Download NLTK data
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet')"

# Stage 3: Production image
FROM base AS production

# Copy requirements and install production dependencies only
COPY requirements*.txt ./

RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy models
RUN python -m spacy download en_core_web_sm

# Download NLTK data
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet')"

# Copy application code
COPY . .

# Install the application in development mode
RUN pip install -e .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash transcriptx && \
    chown -R transcriptx:transcriptx /app
USER transcriptx

# Set default command
CMD ["transcriptx", "--help"] 