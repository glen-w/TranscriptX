# TranscriptX Dependency Management

## Overview

TranscriptX uses a unified dependency management system with two main requirements files:

- **Production**: Complete functionality with all ML/NLP capabilities
- **Development**: Additional tools for testing and development

## Requirements Files

### `requirements.txt`
**Use for**: Complete functionality (production)
- Includes all runtime dependencies: CLI tools, ML/NLP libraries, audio processing, visualization
- Core dependencies: PyTorch, spaCy, transformers, NLTK, scikit-learn
- Audio processing: pyannote.audio, pydub
- Visualization: matplotlib, seaborn, wordcloud
- CLI interface: typer, rich, questionary
- **Size**: ~2.5GB+
- **Startup time**: Slower (ML model loading)

### `requirements-dev.txt`
**Use for**: Development and testing
- Development tools, testing frameworks, code quality tools
- Includes: pytest, pytest-cov, black, ruff, mypy, documentation tools
- **Size**: ~200MB
- **Note**: Install after `requirements.txt` for development work

## NumPy Version Pinning (Important)

**NumPy is intentionally pinned to <2.0** (currently 1.26.4) due to compatibility requirements with spaCy, thinc, and other ML dependencies.

**⚠️ DO NOT ATTEMPT TO UPGRADE NUMPY** - This is an intentional design decision:
- NumPy 2.x has breaking changes incompatible with current ML library versions
- The pinning ensures stable, working functionality
- Core functionality works correctly with NumPy <2.0
- Docker and setup scripts automatically handle this correctly

**If you encounter NumPy-related errors:**
1. Use Docker environment (recommended) - handles dependencies automatically
2. Follow setup scripts which install compatible versions
3. Do NOT manually upgrade NumPy to 2.x

## Deployment Scenarios

### 1. Production Installation (Complete Functionality)
```bash
# Install all dependencies
pip install -r requirements.txt

# Run transcript analysis
./transcriptx.sh
# or
python -m transcriptx.cli.main analyze transcript.json --modules all
```

### 2. Development Environment
```bash
# Install production dependencies first
pip install -r requirements.txt

# Then install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with coverage
pytest --cov=src/transcriptx --cov-report=html
```

### 3. Quick Setup (Recommended)
```bash
# Use the interactive setup script
./scripts/setup_env.sh

# Or use the unified launcher
./transcriptx.sh
```

## Docker Deployments

### WhisperX Service (Audio Transcription)
```bash
# Start WhisperX service for audio transcription
docker-compose -f docker-compose.whisperx.yml --profile whisperx up -d whisperx

# Use with CLI
./transcriptx.sh
# Select "🎤 Transcribe with WhisperX" from menu
```

## Quick Setup

Use the interactive setup script:
```bash
./scripts/setup_env.sh
```

This will guide you through choosing the right environment for your needs.

## Package Configuration

The project uses `pyproject.toml` for package metadata and build configuration, while `requirements.txt` handles actual dependency installation. This separation allows for:
- Clear dependency version control
- Better compatibility with various deployment tools
- Simplified installation process

## Dependency Conflicts Resolved

- **Version conflicts**: All dependencies are pinned to working versions
- **ML compatibility**: PyTorch, spaCy, and transformers versions are compatible
- **NumPy pinning**: Intentionally pinned to <2.0 (1.26.4) for compatibility with spaCy/thinc
- **Stable versions**: All critical ML dependencies use tested, stable versions

## Troubleshooting

### Common Issues

1. **ML models not loading**: Ensure all dependencies are installed with `pip install -r requirements.txt`
2. **NumPy compatibility errors**: NumPy is pinned to 1.26.4 - do NOT upgrade to 2.x
3. **Import errors**: Verify virtual environment is activated and dependencies are installed
4. **spaCy models missing**: Run `python -m spacy download en_core_web_sm` after installing requirements

### Installation Tips

- Always use a virtual environment: `python3.10 -m venv .transcriptx`
- Install NumPy first (before other ML packages) to avoid conflicts
- Use `./transcriptx.sh` for automatic environment setup
- For Docker: Use `docker-compose.whisperx.yml` for WhisperX transcription service

### Performance Considerations

- Full installation: ~2.5GB disk space required
- Memory: 4GB minimum, 8GB+ recommended for ML modules
- Startup time: Initial load may be slower due to ML model loading
- GPU: Optional but recommended for faster processing
