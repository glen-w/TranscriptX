#!/bin/bash
# run_transcriptx.sh - Robust launcher for TranscriptX

export CUDA_VISIBLE_DEVICES=""

# Move to the script's directory (project root)
cd "$(dirname "$0")/.."

# Check for virtual environment
if [ ! -d ".transcriptx" ]; then
  echo "[TranscriptX] Virtual environment .transcriptx not found. Running setup_env.sh..."
  if [ ! -f "scripts/setup_env.sh" ]; then
    echo "[TranscriptX] ERROR: setup_env.sh not found! Cannot set up environment." >&2
    exit 1
  fi
  bash scripts/setup_env.sh || { echo "[TranscriptX] ERROR: setup_env.sh failed." >&2; exit 1; }
fi

# Activate the virtual environment
echo "[TranscriptX] Activating virtual environment (.transcriptx)..."
source .transcriptx/bin/activate || { echo "[TranscriptX] ERROR: Failed to activate .transcriptx." >&2; exit 1; }
echo "[TranscriptX] Virtual environment activated."
echo "[TranscriptX] Python executable: $(which python)"
echo "[TranscriptX] Python version: $(python --version 2>&1)"
echo "[TranscriptX] VIRTUAL_ENV: $VIRTUAL_ENV"

# Check for spaCy models
echo "[TranscriptX] Checking spaCy models..."
if [ -f "check_spacy_models.py" ]; then
    python check_spacy_models.py
else
    echo "[TranscriptX] Warning: check_spacy_models.py not found, skipping model check"
fi

# If no arguments, launch interactive CLI; else, pass arguments to CLI
if [ $# -eq 0 ]; then
  python -m transcriptx.cli.main
else
  python -m transcriptx.cli.main "$@"
fi 