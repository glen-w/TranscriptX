"""
Deduplicate output folders with __N suffixes when safe.

Merges run directories from outputs/<slug>__N into outputs/<slug>
only when both slugs map to the same source_path in .transcriptx_index.json.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple


SUFFIX_RE = re.compile(r"^(?P<base>.+)__\d+$")


def load_index(index_path: Path) -> Dict[str, Any]:
    if not index_path.exists():
        return {"transcripts": {}, "slug_to_key": {}}
    with index_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_index(index_path: Path, index: Dict[str, Any]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2, ensure_ascii=False)


def choose_target_path(base_dir: Path, child_name: str) -> Path:
    candidate = base_dir / child_name
    if not candidate.exists():
        return candidate
    counter = 2
    while True:
        candidate = base_dir / f"{child_name}__dup{counter}"
        if not candidate.exists():
            return candidate
        counter += 1


def merge_runs(base_dir: Path, dup_dir: Path, apply: bool) -> List[Tuple[Path, Path]]:
    moves: List[Tuple[Path, Path]] = []
    for child in sorted(dup_dir.iterdir()):
        target = choose_target_path(base_dir, child.name)
        moves.append((child, target))
        if apply:
            shutil.move(str(child), str(target))
    if apply:
        try:
            dup_dir.rmdir()
        except OSError:
            pass
    return moves


def merge_index_entries(
    index: Dict[str, Any],
    base_slug: str,
    dup_slug: str,
) -> None:
    transcripts = index.get("transcripts", {})
    slug_to_key = index.get("slug_to_key", {})
    base_key = slug_to_key.get(base_slug)
    dup_key = slug_to_key.get(dup_slug)
    if not dup_key:
        return

    base_entry = transcripts.get(base_key) if base_key else None
    dup_entry = transcripts.get(dup_key)
    if dup_entry is None:
        slug_to_key.pop(dup_slug, None)
        index["slug_to_key"] = slug_to_key
        return

    if base_entry is None:
        # Promote dup entry to base slug if base entry missing.
        dup_entry = dict(dup_entry)
        dup_entry["slug"] = base_slug
        transcripts[dup_key] = dup_entry
        slug_to_key[base_slug] = dup_key
    else:
        base_entry = dict(base_entry)
        base_runs = base_entry.get("runs", [])
        dup_runs = dup_entry.get("runs", [])
        merged = list(base_runs)
        for run_id in dup_runs:
            if run_id not in merged:
                merged.append(run_id)
        base_entry["runs"] = merged
        transcripts[base_key] = base_entry

    transcripts.pop(dup_key, None)
    slug_to_key.pop(dup_slug, None)
    index["transcripts"] = transcripts
    index["slug_to_key"] = slug_to_key


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge duplicate output folders with __N suffixes."
    )
    parser.add_argument(
        "--outputs-dir",
        default=str(Path(__file__).resolve().parents[1] / "data" / "outputs"),
        help="Path to outputs directory",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    index_path = outputs_dir / ".transcriptx_index.json"
    index = load_index(index_path)
    transcripts = index.get("transcripts", {})
    slug_to_key = index.get("slug_to_key", {})

    planned = []
    for child in sorted(outputs_dir.iterdir()):
        if not child.is_dir():
            continue
        match = SUFFIX_RE.match(child.name)
        if not match:
            continue
        base_slug = match.group("base")
        base_dir = outputs_dir / base_slug
        if not base_dir.exists():
            planned.append((child.name, base_slug, "skip (no base dir)"))
            continue

        base_key = slug_to_key.get(base_slug)
        dup_key = slug_to_key.get(child.name)
        if not base_key or not dup_key:
            planned.append((child.name, base_slug, "skip (missing index entry)"))
            continue

        base_entry = transcripts.get(base_key, {})
        dup_entry = transcripts.get(dup_key, {})
        if base_entry.get("source_path") != dup_entry.get("source_path"):
            planned.append((child.name, base_slug, "skip (different source_path)"))
            continue

        planned.append((child.name, base_slug, "merge"))

        if args.apply:
            moves = merge_runs(base_dir, child, apply=True)
            merge_index_entries(index, base_slug, child.name)
            print(f"Merged {child.name} -> {base_slug}: {len(moves)} item(s) moved")

    if args.apply:
        save_index(index_path, index)

    if not args.apply:
        print("Dry run. Planned actions:")
        for dup_slug, base_slug, action in planned:
            print(f"- {dup_slug} -> {base_slug}: {action}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
