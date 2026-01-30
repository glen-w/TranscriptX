#!/bin/bash

# Fix TranscriptX Installation Script
# This script fixes the deprecation warning by using modern Python packaging

set -e

echo "🔧 Fixing TranscriptX installation with modern packaging..."

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: No virtual environment detected."
    echo "   It's recommended to run this in a virtual environment."
    echo "   Run: ./transcriptx.sh (which creates .transcriptx environment)"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting. Please run ./transcriptx.sh instead."
        exit 1
    fi
fi

# Uninstall the old version if it exists
echo "🗑️  Removing old installation..."
pip uninstall transcriptx -y 2>/dev/null || true

# Install with modern PEP 517 approach
echo "📦 Installing with modern packaging (PEP 517)..."
pip install -e . --use-pep517

echo "✅ Installation fixed! The deprecation warning should be gone."
echo ""
echo "🚀 You can now run TranscriptX:"
echo "   python -m transcriptx.cli.main"
echo "   or"
echo "   ./transcriptx.sh"
