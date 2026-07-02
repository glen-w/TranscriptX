#!/bin/bash

# TranscriptX Virtual Environment Activation Script

if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run ./scripts/setup_env.sh first to create the environment."
    exit 1
fi

echo "🔧 Activating TranscriptX virtual environment..."
source .venv/bin/activate

echo "✅ Virtual environment activated!"
echo "💡 You can now run TranscriptX commands."
echo "💡 To deactivate, run: deactivate"
echo ""
echo "Available commands:"
echo "  transcriptx --help"
echo "  transcriptx  (launch Streamlit web interface)"
echo "  streamlit run src/transcriptx/web/app.py  (alternative launcher)"
echo "  pytest (if dev dependencies installed)" 