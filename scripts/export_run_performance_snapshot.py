#!/usr/bin/env python3
"""Export a Prometheus textfile snapshot of retained analysis-run performance.

Scans currently retained committed runs under the outputs tree and regenerates
gauge / histogram-bucket metrics (no mtime ingest counters).

Usage (from repo root)::

    python scripts/export_run_performance_snapshot.py
    python scripts/export_run_performance_snapshot.py --output /tmp/tx.prom
    python scripts/export_run_performance_snapshot.py --outputs-dir /path/to/outputs

Environment::

    TRANSCRIPTX_RUN_PERF_EXPORT_PATH   default textfile destination
    TRANSCRIPTX_RUN_PERF_EXPORT_MAX_RUNS
    TRANSCRIPTX_OUTPUT_DIR / TRANSCRIPTX_DATA_DIR  (outputs layout)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate a Prometheus textfile of retained-run performance gauges."
        )
    )
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        default=None,
        help="Transcript outputs root (default: PATHS.outputs_dir)",
    )
    parser.add_argument(
        "--group-outputs-dir",
        type=Path,
        default=None,
        help="Group outputs root (default: PATHS.group_outputs_dir)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help=(
            "Textfile path (default: TRANSCRIPTX_RUN_PERF_EXPORT_PATH or "
            "data/state/run_performance_snapshot.prom)"
        ),
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Max committed runs to include (default from env or 10000)",
    )
    args = parser.parse_args(argv)

    from transcriptx.core.observability.run_performance.exporter import (
        config_from_env,
        export_retained_run_snapshot,
    )

    config = config_from_env(
        outputs_dir=args.outputs_dir,
        group_outputs_dir=args.group_outputs_dir,
        textfile_path=args.output,
        max_runs=args.max_runs,
    )
    result = export_retained_run_snapshot(config)
    print(
        f"Wrote {result.textfile_path} "
        f"(runs={result.runs_exported}, candidates={result.candidates_seen}, "
        f"sidecar={result.runs_with_sidecar}, "
        f"no_sidecar={result.runs_without_sidecar}, "
        f"errors={result.scan_errors}, truncated={result.truncated})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
