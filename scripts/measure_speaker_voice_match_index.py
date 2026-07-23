#!/usr/bin/env python3
"""Measure Stage 9 voice match reference-environment advisories.

Runs a synthetic 500-profile × multi-ref matmul benchmark and writes results
for docs/dev/speaker_voice_match_index_gate.md.

Usage:
  python scripts/measure_speaker_voice_match_index.py
  python scripts/measure_speaker_voice_match_index.py --out artifacts/voice_index_measure.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("artifacts/voice_index_measure.json"),
    )
    parser.add_argument("--profiles", type=int, default=500)
    parser.add_argument("--refs-per-profile", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    repo_src = Path(__file__).resolve().parents[1] / "src"
    if repo_src.is_dir() and str(repo_src) not in sys.path:
        sys.path.insert(0, str(repo_src))

    from transcriptx.core.speaker_profiles.voice.ref_index import measure_scan_vs_index

    report = measure_scan_vs_index(
        profile_count=args.profiles,
        refs_per_profile=args.refs_per_profile,
        seed=args.seed,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
