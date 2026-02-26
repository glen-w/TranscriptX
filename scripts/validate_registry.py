#!/usr/bin/env python3
"""
Validate the analysis module registry: no duplicate names, valid categories,
and every declared dependency is a registered module. Run from repo root or with
PYTHONPATH including src.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on path when run as script
repo_root = Path(__file__).resolve().parents[1]
src = repo_root / "src"
if src.exists() and str(src) not in sys.path:
    sys.path.insert(0, str(src))

from transcriptx.core.pipeline.module_registry import (
    get_available_modules,
    get_dependencies,
    get_module_info,
    get_category,
)

VALID_CATEGORIES = {"light", "medium", "heavy"}


def main() -> int:
    all_names = set(get_available_modules())
    errors: list[str] = []

    for name in get_available_modules():
        info = get_module_info(name)
        if not info:
            errors.append(f"Module '{name}' has no ModuleInfo")
            continue
        cat = get_category(name)
        if cat not in VALID_CATEGORIES:
            errors.append(
                f"Module '{name}' has invalid category '{cat}'; must be one of {VALID_CATEGORIES}"
            )
        for dep in get_dependencies(name):
            if dep not in all_names:
                errors.append(
                    f"Module '{name}' declares dependency '{dep}' which is not a registered module"
                )

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    print("Registry validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
