"""CLI: run selected analysis modules across the managed library (catch-up).

Invoked as:

- ``transcriptx analyze-modules …``
- ``python -m transcriptx.analyze_modules …``

Default modules: ``transcript_output`` (human-readable transcripts) and
``llm_summary``. Speakers need not be identified. Transcripts whose newest
committed run already executed every requested module are skipped.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

_DEFAULT_MODULES = ("transcript_output", "llm_summary")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transcriptx analyze-modules",
        description=(
            "Run selected modules on managed transcripts that are missing them. "
            "Default: transcript_output + llm_summary, allowing unnamed speakers."
        ),
    )
    parser.add_argument(
        "--modules",
        default=",".join(_DEFAULT_MODULES),
        metavar="IDS",
        help=(
            "Comma-separated module ids "
            f"(default: {','.join(_DEFAULT_MODULES)})."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("quick", "full"),
        default="full",
        help="Pipeline mode (default: full).",
    )
    parser.add_argument(
        "--preset",
        dest="analysis_preset",
        choices=("quick", "balanced", "thorough", "custom"),
        default="custom",
        help="UI analysis preset persisted on the run (default: custom).",
    )
    parser.add_argument(
        "--allow-unnamed-speakers",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Allow diarized SPEAKER_xx labels (default: true). "
            "Use --no-allow-unnamed-speakers to require named speakers."
        ),
    )
    parser.add_argument(
        "--include-unidentified-speakers",
        action="store_true",
        help="Include unidentified speakers in speaker-scoped modules.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run even when the newest run already has every requested module.",
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
        help="List targets without running analysis.",
    )
    return parser.parse_args(argv)


def _parse_modules(raw: str) -> list[str]:
    modules = [m.strip() for m in str(raw).split(",") if m.strip()]
    if not modules:
        raise ValueError("--modules was empty after parsing")
    return modules


def _newest_run_dir(output_root: Path) -> Path | None:
    from transcriptx.app.corpus_inventory.service import newest_run_dir

    if not output_root.exists():
        return None
    return newest_run_dir(output_root)


def _modules_present_in_newest_run(
    transcript_path: Path, required: Sequence[str]
) -> set[str]:
    """Return the subset of ``required`` already listed in newest modules_run."""
    from transcriptx.core.utils._path_core import get_transcript_dir

    out_root = Path(get_transcript_dir(str(transcript_path)))
    run_dir = _newest_run_dir(out_root)
    if run_dir is None:
        return set()
    results_path = run_dir / "run_results.json"
    if not results_path.is_file():
        return set()
    try:
        payload = json.loads(results_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(payload, dict):
        return set()
    ran = payload.get("modules_run") or []
    if not isinstance(ran, list):
        return set()
    ran_set = {str(m) for m in ran}
    return {m for m in required if m in ran_set}


def _missing_modules(transcript_path: Path, required: Sequence[str]) -> list[str]:
    present = _modules_present_in_newest_run(transcript_path, required)
    return [m for m in required if m not in present]


def _discover_targets(
    *,
    modules: Sequence[str],
    force: bool,
) -> list[tuple[Path, list[str]]]:
    from transcriptx.core.utils.file_discovery import discover_managed_transcript_paths

    targets: list[tuple[Path, list[str]]] = []
    for path in discover_managed_transcript_paths():
        p = Path(path)
        if force:
            targets.append((p, list(modules)))
            continue
        missing = _missing_modules(p, modules)
        if missing:
            # Re-run the full requested set so one run carries both artifacts.
            targets.append((p, list(modules)))
    targets.sort(key=lambda item: str(item[0]))
    return targets


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    from transcriptx._bootstrap import bootstrap

    bootstrap()

    try:
        modules = _parse_modules(args.modules)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    targets = _discover_targets(modules=modules, force=bool(args.force))
    if args.max and args.max > 0:
        targets = targets[: int(args.max)]

    print(
        f"module-backlog: {len(targets)} transcript(s) "
        f"(modules={modules!r}, allow_unnamed_speakers="
        f"{bool(args.allow_unnamed_speakers)}, force={bool(args.force)})"
    )
    if args.dry_run:
        for path, needed in targets:
            print(f"  would analyze: {path} modules={needed}")
        return 0

    if not targets:
        print("ok: nothing to analyze")
        return 0

    from transcriptx.app.models.requests import AnalysisRequest
    from transcriptx.app.workflows.analysis import run_analysis

    ok = 0
    failed = 0
    for index, (path, needed) in enumerate(targets, start=1):
        print(
            f"[{index}/{len(targets)}] analyze {path} modules={needed}",
            file=sys.stderr,
        )
        result = run_analysis(
            AnalysisRequest(
                transcript_path=path,
                mode=str(args.mode),
                analysis_preset=args.analysis_preset,
                modules=needed,
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
