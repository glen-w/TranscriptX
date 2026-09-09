"""CLI: auto-identify speakers on managed (or local) transcripts.

Invoked as ``python -m transcriptx.identify_speakers`` (not ``transcriptx <subcommand>``).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from transcriptx.core.speaker_profiles.identify.service import identify_many
from transcriptx.core.speaker_profiles.identify.settings import load_identify_settings


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Identify unnamed diarized speakers using voice match and text "
            "patterns. Optionally write speaker-map names and/or profile links."
        ),
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        default=None,
        metavar="FILE",
        help="Transcript JSON to identify (repeatable).",
    )
    parser.add_argument(
        "--all-unnamed",
        action="store_true",
        help="Scan the managed library for transcripts with unnamed speakers.",
    )
    name_group = parser.add_mutually_exclusive_group()
    name_group.add_argument(
        "--auto-name",
        dest="auto_name",
        action="store_true",
        default=None,
        help="Write display names to the speaker-map sidecar.",
    )
    name_group.add_argument(
        "--no-auto-name",
        dest="auto_name",
        action="store_false",
        help="Do not write speaker-map names.",
    )
    link_group = parser.add_mutually_exclusive_group()
    link_group.add_argument(
        "--auto-link",
        dest="auto_link",
        action="store_true",
        default=None,
        help="Create longitudinal profile links for matched profiles.",
    )
    link_group.add_argument(
        "--no-auto-link",
        dest="auto_link",
        action="store_false",
        help="Do not create profile links.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyse and print decisions; do not write maps or links.",
    )
    return parser.parse_args(argv)


def _library_unnamed_paths() -> list[Path]:
    from transcriptx.io.speaker_map_resolver import (
        is_effective_speaker_name,
        SpeakerMapResolver,
    )
    from transcriptx.core.utils.file_discovery import discover_managed_transcript_paths

    resolver = SpeakerMapResolver()
    out: list[Path] = []
    for path in discover_managed_transcript_paths():
        state = resolver.load_mapping(path)
        try:
            from transcriptx.core.speaker_profiles.resolver import (
                load_transcript_segments,
            )
            from transcriptx.io.speaker_map_resolver import normalize_diarized_id

            segs = load_transcript_segments(path)
        except Exception:
            continue
        keys: set[str] = set()
        for segment in segs:
            key = normalize_diarized_id(
                segment.get("speaker_diarized_id") or segment.get("speaker")
            )
            if key:
                keys.add(key)
        ignored = set(state.ignored_speakers)
        unnamed = [
            k
            for k in keys
            if k not in ignored
            and not is_effective_speaker_name(k, state.speaker_map.get(k, ""))
        ]
        if unnamed:
            out.append(Path(path))
    return out


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    from transcriptx._bootstrap import bootstrap

    bootstrap()

    settings = load_identify_settings()
    auto_name = settings.auto_name if args.auto_name is None else bool(args.auto_name)
    auto_link = settings.auto_link if args.auto_link is None else bool(args.auto_link)
    if args.auto_name is True and args.auto_link is None:
        auto_link = True

    paths: list[Path] = []
    if args.paths:
        paths.extend(Path(p).expanduser() for p in args.paths)
    if args.all_unnamed:
        paths.extend(_library_unnamed_paths())
    # de-dupe preserving order
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)

    if not unique:
        print("ERROR: pass --path FILE and/or --all-unnamed", file=sys.stderr)
        return 2

    if not auto_name and not auto_link and not args.dry_run:
        print(
            "WARNING: auto-name and auto-link are both off; "
            "writing artefact only (use --auto-name / --auto-link).",
            file=sys.stderr,
        )

    results = identify_many(
        unique,
        auto_name=auto_name,
        auto_link=auto_link,
        dry_run=bool(args.dry_run),
        style_only_apply=settings.style_only_apply,
    )
    failed = 0
    for result in results:
        label = Path(result.transcript_path).name
        if result.error:
            print(f"ERROR: {label}: {result.error}", file=sys.stderr)
            failed += 1
            continue
        print(
            f"  {label}: named={result.named_count} linked={result.linked_count} "
            f"skipped={result.skipped_count}"
            + (" (dry-run)" if result.dry_run else "")
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
