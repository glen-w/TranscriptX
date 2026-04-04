#!/usr/bin/env python3
"""
Slim cold vs warm timing baseline for pipeline import and minimal resolution.

Run from repo root: ``python scripts/bench_pipeline_cold_warm.py``
(Uses subprocess for a second cold-ish process; warm is same interpreter.)
"""

from __future__ import annotations

import subprocess
import sys
import time


def main() -> None:
    cold_code = """
import time
t0 = time.perf_counter()
import transcriptx.core.pipeline.pipeline  # noqa: F401
print(f"cold_import_s {time.perf_counter() - t0:.4f}")
"""
    r = subprocess.run(
        [sys.executable, "-c", cold_code],
        capture_output=True,
        text=True,
        check=False,
    )
    print(r.stdout.strip() or r.stderr)

    t0 = time.perf_counter()
    import transcriptx.core.pipeline.pipeline  # noqa: F401, E402

    print(f"warm_import_s {time.perf_counter() - t0:.4f}")


if __name__ == "__main__":
    main()
