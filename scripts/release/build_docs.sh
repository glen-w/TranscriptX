#!/usr/bin/env bash
# Maintainer: build Sphinx HTML docs into docs/_build/html.
# Usage (from repo root): bash scripts/release/build_docs.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ ! -f docs/conf.py ]]; then
  echo "error: docs/conf.py missing — Sphinx tree not present" >&2
  exit 1
fi

if ! command -v sphinx-build >/dev/null 2>&1; then
  echo "error: sphinx-build not found. Install with: pip install -e '.[docs]'" >&2
  exit 1
fi

OUT="${DOCS_BUILD_DIR:-docs/_build/html}"
mkdir -p "$(dirname "$OUT")"
echo "Building Sphinx HTML → ${OUT}"
# Warnings are allowed during the first revive; tighten once RTD is live.
sphinx-build -b html docs "$OUT"
echo "OK: open ${OUT}/index.html"
