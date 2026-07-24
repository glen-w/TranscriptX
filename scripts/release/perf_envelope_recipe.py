#!/usr/bin/env python3
"""Print a reproducible performance-envelope measurement recipe (0.9.7).

Maintainer tooling — does not run benchmarks itself. Records identity context
and points at docs/dev/performance_envelopes_1_0.md. Write raw notes under
ignored `.local/` scratch.

Usage (repo root):
  python3 scripts/release/perf_envelope_recipe.py
  make perf-envelopes
"""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    try:
        import transcriptx

        version = transcriptx.__version__
    except Exception as exc:  # pragma: no cover - environment dependent
        version = f"(unavailable: {exc})"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("TranscriptX performance envelope recipe")
    print(f"  timestamp_utc: {now}")
    print(f"  package_version: {version}")
    print(f"  python: {sys.version.split()[0]}")
    print(f"  platform: {platform.platform()}")
    print(f"  machine: {platform.machine()}")
    print()
    print("Corpus classes (see docs/dev/performance_envelopes_1_0.md):")
    print("  Small: 1 short meeting")
    print("  Medium: ~5–10 transcripts, default (Balanced) preset")
    print("  Large-for-1.0: ~50 library + one multi-member group")
    print()
    print("Steps:")
    print("  1) Record Docker vs native and host RAM/CPU class.")
    print("  2) Time GUI cold startup to interactive Home.")
    print("  3) Managed-import Small/Medium; note wall + data-root disk delta.")
    print("  4) Run default preset; read <run>/.transcriptx/run_performance.json")
    print("     and module duration_ms in run_results.json.")
    print("  5) Clock time-to-first-useful (import Small → Overview/Insights).")
    print("  6) docker images / docker history for image size (if Docker).")
    print("  7) One group of 3–5 members; record group sidecar wall.")
    print("  8) Note fail-closed behaviour for disk/RAM/model insufficiency.")
    print()
    print("Write raw notes to: .local/perf_envelopes_<date>.md (gitignored)")
    print("Curate measured-or-tagged rows into docs/dev/performance_envelopes_1_0.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
