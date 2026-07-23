#!/usr/bin/env python3
"""Eval harness scaffold for voice match threshold calibration.

Builds same/different speaker pairs from trusted confirmed links when a
speaker_profiles tree is provided. Prefer grouping splits by profile_id and
managed_transcript_id to avoid pair leakage.

Usage:
  python scripts/eval_speaker_voice_match.py --root /path/to/speaker_profiles
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("artifacts/voice_eval.json"))
    args = parser.parse_args()
    root = args.root
    emb_dir = root / "voice" / "embeddings"
    by_profile: dict[str, list[str]] = {}
    if emb_dir.is_dir():
        for path in emb_dir.glob("*.voice_embedding.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("eligibility_state") != "eligible":
                continue
            if data.get("trust_level") not in ("manual", "promoted"):
                continue
            by_profile.setdefault(data["profile_id"], []).append(data["embedding_id"])
    report = {
        "profiles_with_eligible_embeddings": len(by_profile),
        "eligible_embedding_count": sum(len(v) for v in by_profile.values()),
        "note": (
            "Provisional thresholds remain in voice/thresholds.py until this "
            "harness is run on a labeled library with speaker/recording-held splits."
        ),
        "threshold_policy_id": "voice_threshold.v1",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
