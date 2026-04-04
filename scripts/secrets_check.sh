#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

fail=0

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if git ls-files -- "whisperx.env" | grep -q .; then
        echo "ERROR: whisperx.env is tracked. Remove with: git rm --cached whisperx.env"
        fail=1
    fi

    hf_hits="$(git grep -n -E "hf_[A-Za-z0-9]{20,}" || true)"
    if [ -n "$hf_hits" ]; then
        echo "ERROR: Potential Hugging Face tokens found in tracked files:"
        echo "$hf_hits"
        fail=1
    fi
else
    echo "INFO: Not a git repository; skipping tracked-file checks."
fi

if [ "$fail" -ne 0 ]; then
    exit 1
fi

echo "OK: No tracked whisperx.env and no hf_ tokens found."
