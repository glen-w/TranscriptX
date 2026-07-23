#!/usr/bin/env python3
"""Eval harness for voice match threshold calibration.

Builds same/different speaker pairs from trusted confirmed embeddings when a
speaker_profiles tree is provided. Prefer grouping splits by profile_id and
managed_transcript_id to avoid pair leakage.

Usage:
  python scripts/eval_speaker_voice_match.py --root /path/to/speaker_profiles
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("artifacts/voice_eval.json"))
    parser.add_argument("--max-same-pairs", type=int, default=5000)
    parser.add_argument("--max-different-pairs", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    # Allow running from a checkout without installed editable package.
    repo_src = Path(__file__).resolve().parents[1] / "src"
    if repo_src.is_dir() and str(repo_src) not in sys.path:
        sys.path.insert(0, str(repo_src))

    from transcriptx.core.speaker_profiles.voice.eval_metrics import (
        evaluate_speaker_profiles_root,
        write_eval_report,
    )

    report = evaluate_speaker_profiles_root(
        args.root,
        max_same_pairs=args.max_same_pairs,
        max_different_pairs=args.max_different_pairs,
        seed=args.seed,
    )
    write_eval_report(report, args.out)
    summary = {
        "threshold_policy_id": report.threshold_policy_id,
        "profiles_with_eligible_embeddings": report.profiles_with_eligible_embeddings,
        "eligible_embedding_count": report.eligible_embedding_count,
        "same_pair_count": report.same_pair_count,
        "different_pair_count": report.different_pair_count,
        "far_at_tau_candidate": report.far_at_tau_candidate,
        "frr_at_tau_candidate": report.frr_at_tau_candidate,
        "recommended_action": report.recommended_action,
        "out": str(args.out),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
