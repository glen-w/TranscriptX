"""CLI: run thorough analysis on managed transcripts that are ready but unanalyzed.

Invoked as:

- ``transcriptx analyze-backlog …``
- ``python -m transcriptx.analyze_backlog …``

Discovers managed library transcripts, optionally requires a complete speaker
map and/or specific named speakers, skips those that already have analysis
outputs, and runs analysis (default: thorough / full).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transcriptx analyze-backlog",
        description=(
            "Analyze managed transcripts that have no analysis outputs yet. "
            "Default filter: speaker map status complete."
        ),
    )
    parser.add_argument(
        "--preset",
        dest="analysis_preset",
        choices=("quick", "balanced", "thorough", "custom"),
        default="thorough",
        help="Analysis preset (default: thorough).",
    )
    parser.add_argument(
        "--mode",
        choices=("quick", "full"),
        default="full",
        help="Pipeline mode (default: full).",
    )
    parser.add_argument(
        "--require-complete-speakers",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Only analyze transcripts whose speaker map is complete "
            "(default: true). Use --no-require-complete-speakers to include others."
        ),
    )
    parser.add_argument(
        "--require-named-speaker",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "Only analyze transcripts that include this display name among "
            "effective named speakers (case-insensitive). Repeatable; all "
            "names must match."
        ),
    )
    parser.add_argument(
        "--allow-unnamed-speakers",
        action="store_true",
        help="Pass through to analyze when speakers are still diarized labels.",
    )
    parser.add_argument(
        "--include-unidentified-speakers",
        action="store_true",
        help="Include unidentified speakers in speaker-scoped modules.",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        metavar="N",
        help="Analyze at most N transcripts (0 = no limit).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List backlog targets without running analysis.",
    )
    return parser.parse_args(argv)


def _effective_named_display_names(transcript_path: Path) -> set[str]:
    """Return casefolded effective display names from the speaker map sidecar."""
    from transcriptx.io.speaker_map_resolver import (
        SpeakerMapResolver,
        is_effective_speaker_name,
    )

    state = SpeakerMapResolver().load_mapping(transcript_path)
    ignored = set(state.ignored_speakers)
    names: set[str] = set()
    for speaker_id, display_name in state.speaker_map.items():
        if speaker_id in ignored:
            continue
        if not is_effective_speaker_name(speaker_id, display_name):
            continue
        folded = str(display_name).strip().casefold()
        if folded:
            names.add(folded)
    return names


def _has_required_named_speakers(
    transcript_path: Path, required_names: Sequence[str]
) -> bool:
    if not required_names:
        return True
    present = _effective_named_display_names(transcript_path)
    for name in required_names:
        if str(name).strip().casefold() not in present:
            return False
    return True


def _discover_backlog(
    *,
    require_complete_speakers: bool,
    require_named_speakers: Sequence[str] = (),
) -> list[Path]:
    from transcriptx.app.controllers.library_controller import LibraryController

    required = [n for n in require_named_speakers if str(n).strip()]
    backlog: list[Path] = []
    for meta in LibraryController().list_transcripts():
        if meta.has_analysis_outputs:
            continue
        if require_complete_speakers and meta.speaker_map_status != "complete":
            continue
        path = Path(meta.path)
        if required and not _has_required_named_speakers(path, required):
            continue
        backlog.append(path)
    backlog.sort(key=lambda p: str(p))
    return backlog


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    from transcriptx._bootstrap import bootstrap

    bootstrap()

    required_names = list(args.require_named_speaker or [])
    targets = _discover_backlog(
        require_complete_speakers=bool(args.require_complete_speakers),
        require_named_speakers=required_names,
    )
    if args.max and args.max > 0:
        targets = targets[: int(args.max)]

    named_note = (
        f", require_named_speakers={required_names!r}" if required_names else ""
    )
    print(
        f"backlog: {len(targets)} transcript(s) "
        f"(require_complete_speakers={bool(args.require_complete_speakers)}"
        f"{named_note})"
    )
    if args.dry_run:
        for path in targets:
            print(f"  would analyze: {path}")
        return 0

    if not targets:
        print("ok: nothing to analyze")
        return 0

    from transcriptx.app.models.requests import AnalysisRequest
    from transcriptx.app.workflows.analysis import run_analysis

    ok = 0
    failed = 0
    for index, path in enumerate(targets, start=1):
        print(f"[{index}/{len(targets)}] analyze {path}", file=sys.stderr)
        result = run_analysis(
            AnalysisRequest(
                transcript_path=path,
                mode=str(args.mode),
                analysis_preset=args.analysis_preset,
                modules=None,
                allow_unnamed_speakers=bool(args.allow_unnamed_speakers),
                include_unidentified_speakers=bool(
                    args.include_unidentified_speakers
                ),
            )
        )
        for warning in result.warnings:
            print(f"warning: {warning}", file=sys.stderr)
        for err in result.errors:
            print(f"ERROR: {err}", file=sys.stderr)
        if result.success:
            ok += 1
            print(f"ok: {path} status={result.status} run_dir={result.run_dir}")
        else:
            failed += 1
            print(
                f"failed: {path} status={result.status}",
                file=sys.stderr,
            )

    print(f"done: ok={ok} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
