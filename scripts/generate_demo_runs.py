#!/usr/bin/env python3
"""Maintainer CLI: validate demo pack and (re)generate deterministic demo runs.

In-process install uses the same generate path. This script is for CI/maintainers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root
if __name__ == "__main__" and __package__ is None:
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root / "src"))

from transcriptx.demo.pack_loader import PackValidationError, load_and_validate_pack
from transcriptx.demo.service import (
    install_demo_project,
    plan_install,
    status_demo_project,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate pack resources and exit",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install demo into the current data root (idempotent)",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Print install plan",
    )
    args = parser.parse_args(argv)

    try:
        pack = load_and_validate_pack()
    except PackValidationError as exc:
        print(f"PACK INVALID: {exc}", file=sys.stderr)
        return 2
    print(
        f"Pack OK: {pack.pack_id}@{pack.pack_version} "
        f"({len(pack.transcripts)} transcripts, hash={pack.pack_hash[:12]})"
    )
    if args.plan:
        plan = plan_install()
        print("Plan:", plan.operation, plan.steps)
    if args.validate_only:
        return 0
    if args.install:
        status = status_demo_project()
        print("Status before:", status.kind.value, status.detail)
        result = install_demo_project()
        print("Result:", result.status.value, result.detail)
        for err in result.errors:
            print("  error:", err, file=sys.stderr)
        return 0 if result.ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
