#!/usr/bin/env python3
"""Create / verify / restore full-workspace backup ZIPs.

Thin shim around ``transcriptx backup`` / ``python -m transcriptx.backup``.
Prefer the console subcommand when the package is installed; this script remains
for large-corpus ops from a source checkout.

Examples:
    transcriptx backup create
    uv run python scripts/workspace_backup.py create --dest /safe/ws.zip --force
    uv run python scripts/workspace_backup.py verify /safe/ws.zip
    uv run python scripts/workspace_backup.py restore /safe/ws.zip --dry-run
    uv run python scripts/workspace_backup.py restore /safe/ws.zip --yes
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from transcriptx.backup import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
