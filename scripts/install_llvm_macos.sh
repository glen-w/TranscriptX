#!/bin/bash
# One-time setup: install LLVM so llvmlite (numba/librosa) can build on macOS.
# Run: source scripts/install_llvm_macos.sh   (or . scripts/install_llvm_macos.sh)
# Then: pip install -r requirements.txt

set -e
[[ "$OSTYPE" != "darwin"* ]] && { echo "macOS only."; exit 1; }
command -v brew &>/dev/null || { echo "Install Homebrew: https://brew.sh"; exit 1; }

if ! brew list llvm &>/dev/null; then
  echo "Installing LLVM (this may take a few minutes)..."
  brew install llvm
fi

LLVM_PREFIX=$(brew --prefix llvm)
export LLVM_CONFIG="${LLVM_PREFIX}/bin/llvm-config"
export CMAKE_PREFIX_PATH="${LLVM_PREFIX}"
export LLVM_DIR="${LLVM_PREFIX}/lib/cmake/llvm"
export PATH="${LLVM_PREFIX}/bin:$PATH"

echo "LLVM ready. Env set for this shell. Re-run your pip install."
