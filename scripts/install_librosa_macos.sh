#!/bin/bash

# Helper script to install librosa on macOS with LLVM support
# This script handles the LLVM dependency issue for llvmlite (numba dependency)

set -e

echo "🔧 Installing librosa on macOS"
echo "=============================="
echo ""

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "⚠️  This script is designed for macOS. On other platforms, use:"
    echo "   pip install librosa>=0.10.0"
    exit 1
fi

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew is not installed."
    echo "   Please install Homebrew first: https://brew.sh"
    exit 1
fi

# Check if LLVM is installed via Homebrew
if ! brew list llvm &> /dev/null; then
    echo "📦 LLVM is not installed. Installing via Homebrew..."
    echo "   This may take a few minutes..."
    brew install llvm
    echo "✅ LLVM installed"
else
    echo "✅ LLVM is already installed"
fi

# Get LLVM prefix
LLVM_PREFIX=$(brew --prefix llvm)
LLVM_CONFIG="${LLVM_PREFIX}/bin/llvm-config"

if [ ! -f "$LLVM_CONFIG" ]; then
    echo "❌ Could not find llvm-config at $LLVM_CONFIG"
    exit 1
fi

echo ""
echo "🔧 Setting up environment variables..."
export LLVM_CONFIG="$LLVM_CONFIG"
export CMAKE_PREFIX_PATH="$LLVM_PREFIX"
export PATH="${LLVM_PREFIX}/bin:$PATH"

echo "   LLVM_CONFIG=$LLVM_CONFIG"
echo "   CMAKE_PREFIX_PATH=$CMAKE_PREFIX"
echo ""

# Try to use pre-built wheels first (faster, no compilation needed)
echo "📦 Attempting to install librosa using pre-built wheels..."
if pip install --prefer-binary librosa>=0.10.0; then
    echo "✅ librosa installed successfully using pre-built wheels!"
    exit 0
fi

echo ""
echo "⚠️  Pre-built wheels not available, building from source..."
echo "   This may take several minutes..."

# If pre-built wheels fail, try building with LLVM environment variables
if pip install librosa>=0.10.0; then
    echo "✅ librosa installed successfully!"
else
    echo ""
    echo "❌ Installation failed. You can try manually:"
    echo "   export LLVM_CONFIG=$LLVM_CONFIG"
    echo "   export CMAKE_PREFIX_PATH=$CMAKE_PREFIX"
    echo "   pip install librosa>=0.10.0"
    exit 1
fi
