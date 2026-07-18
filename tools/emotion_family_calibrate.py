#!/usr/bin/env python3
"""Emotion-family Phase 5 calibration helper (does not auto-promote).

Usage:
  python tools/emotion_family_calibrate.py --set calibration
  python tools/emotion_family_calibrate.py --set held_out --check-gates

This script is intentionally offline-friendly: without transformers models it
prints fixture coverage against promotion_gates.json and refuses promotion.
Live scoring requires the emotion_transformers extra and local model cache.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "emotion_family"
GATES_PATH = FIXTURE_ROOT / "promotion_gates.json"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def fixture_coverage_report(set_name: str) -> dict:
    seed = _load_json(FIXTURE_ROOT / set_name / "seed.json")
    gates = _load_json(GATES_PATH)
    tones = Counter(
        (seg.get("expected") or {}).get("tone") for seg in seed.get("segments") or []
    )
    required = gates.get("minimum_fixture_counts") or {}
    missing = {
        tone: need - tones.get(tone, 0)
        for tone, need in required.items()
        if tones.get(tone, 0) < need
    }
    return {
        "set": set_name,
        "segment_count": len(seed.get("segments") or []),
        "tone_counts": dict(tones),
        "missing_vs_gates": missing,
        "coverage_ok": not missing,
        "promotion_status": gates.get("status"),
        "note": gates.get("note"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--set",
        choices=("calibration", "held_out"),
        default="calibration",
        help="Which fixture set to inspect",
    )
    parser.add_argument(
        "--check-gates",
        action="store_true",
        help="Exit non-zero if fixture coverage fails predefined minimums",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Always refused: promotion requires a separate held-out metric run",
    )
    args = parser.parse_args(argv)

    if args.promote:
        print(
            "REFUSED: auto-promotion is disabled. "
            "Publish threshold_profile_v1 only after held-out metrics meet "
            f"{GATES_PATH} and Hub revisions are pinned (not 'main').",
            file=sys.stderr,
        )
        return 2

    report = fixture_coverage_report(args.set)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.check_gates and not report["coverage_ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
