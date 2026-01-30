#!/bin/bash

# TranscriptX Codebase Cleanup Script
# This script helps maintain a clean codebase by removing temporary files and organizing the project structure.

set -e

echo "🧹 Starting TranscriptX codebase cleanup..."

# Remove Python cache files
echo "📦 Removing Python cache files..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true

# Remove system files
echo "🖥️  Removing system files..."
find . -name ".DS_Store" -delete 2>/dev/null || true
find . -name "Thumbs.db" -delete 2>/dev/null || true

# Remove temporary files
echo "🗑️  Removing temporary files..."
find . -name "*.tmp" -delete 2>/dev/null || true
find . -name "*.temp" -delete 2>/dev/null || true
find . -name "*.swp" -delete 2>/dev/null || true
find . -name "*.swo" -delete 2>/dev/null || true

# Remove build artifacts
echo "🔨 Removing build artifacts..."
rm -rf build/ 2>/dev/null || true
rm -rf dist/ 2>/dev/null || true
rm -rf *.egg-info/ 2>/dev/null || true

# Remove coverage reports
echo "📊 Removing coverage reports..."
rm -f coverage.xml 2>/dev/null || true
rm -rf htmlcov/ 2>/dev/null || true
rm -rf .coverage* 2>/dev/null || true

# Remove pytest cache
echo "🧪 Removing pytest cache..."
rm -rf .pytest_cache/ 2>/dev/null || true

# Remove mypy cache
echo "🔍 Removing mypy cache..."
find . -name ".mypy_cache" -type d -exec rm -rf {} + 2>/dev/null || true

# Remove node_modules (if not needed)
if [ "$1" = "--aggressive" ]; then
    echo "📦 Removing node_modules (aggressive mode)..."
    rm -rf node_modules/ 2>/dev/null || true
fi

# Clean up empty directories
echo "📁 Removing empty directories..."
find . -type d -empty -delete 2>/dev/null || true

echo "✅ Cleanup completed successfully!"
echo ""
echo "📋 Summary of cleaned items:"
echo "  - Python cache files (__pycache__, *.pyc, *.pyo)"
echo "  - System files (.DS_Store, Thumbs.db)"
echo "  - Temporary files (*.tmp, *.temp, *.swp, *.swo)"
echo "  - Build artifacts (build/, dist/, *.egg-info/)"
echo "  - Coverage reports (coverage.xml, htmlcov/, .coverage*)"
echo "  - Pytest cache (.pytest_cache/)"
echo "  - Mypy cache (.mypy_cache/)"
echo "  - Empty directories"
echo ""
echo "💡 Tip: Run with --aggressive flag to also remove node_modules" 