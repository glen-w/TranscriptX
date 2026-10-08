"""CLI: run thorough analysis on managed transcripts that are ready but unanalyzed.

Invoked as:

- ``transcriptx analyze-backlog …``
- ``python -m transcriptx.analyze_backlog …``

Discovers managed library transcripts, optionally requires a complete speaker
map and/or specific named speakers / a minimum named-speaker count, skips those
that already have a completed run for the requested preset (thorough =
``is_complete_analysis_run``), and runs analysis (default: thorough / full).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


_LLM_EFFORT_TARGETS = (
    "llm_summary",
    "llm_speaker_summary",
    "llm_action_items",
    "llm_custom_qa",
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transcriptx analyze-backlog",
        description=(
            "Analyze managed transcripts that lack a completed run for the "
            "requested preset. Default filter: speaker map status complete."
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
        "--min-named-speakers",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Only analyze transcripts with at least N effective named speakers "
            "(default: 1). Use with --require-named-speaker Glen and N=2 for "
            "Glen plus at least one other identified speaker."
        ),
    )
    parser.add_argument(
        "--llm-effort",
        choices=("low", "medium", "high", "max"),
        default=None,
        help=(
            "Override Ollama effort for llm_summary, llm_speaker_summary, "
            "llm_action_items, and llm_custom_qa for this process "
            "(default: leave project/config values unchanged)."
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


def _named_speaker_count(transcript_path: Path) -> int:
    return len(_effective_named_display_names(transcript_path))


def _iter_run_results_payloads(transcript_path: Path):
    """Yield run_results.json dicts under the transcript output root."""
    from transcriptx.core.utils._path_core import get_transcript_dir

    out_root = Path(get_transcript_dir(str(transcript_path)))
    if not out_root.is_dir():
        return
    try:
        children = list(out_root.iterdir())
    except OSError:
        return
    for child in children:
        if not child.is_dir() or child.name.startswith("."):
            continue
        path = child / "run_results.json"
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(payload, dict):
            yield payload


def _has_completed_preset_run(transcript_path: Path, preset: str) -> bool:
    """True when any run under the transcript already completed for ``preset``."""
    from transcriptx.core.utils.analysis_picker_status import (
        is_complete_analysis_run,
        run_execution_status,
    )

    wanted = str(preset or "").strip().lower()
    if not wanted:
        return False
    for payload in _iter_run_results_payloads(transcript_path):
        if wanted == "thorough":
            if is_complete_analysis_run(payload):
                return True
            continue
        run_preset = str(payload.get("analysis_preset") or "").strip().lower()
        if run_preset != wanted:
            continue
        if run_execution_status(payload) == "completed":
            return True
    return False


def _apply_llm_effort(effort: str) -> None:
    """Set Ollama effort on the live analysis LLM module configs for this process."""
    from transcriptx.core.utils.config import get_config

    analysis = get_config().analysis
    for attr in _LLM_EFFORT_TARGETS:
        module_cfg = getattr(analysis, attr, None)
        if module_cfg is None or not hasattr(module_cfg, "effort"):
            continue
        setattr(module_cfg, "effort", effort)


def _discover_backlog(
    *,
    analysis_preset: str,
    require_complete_speakers: bool,
    require_named_speakers: Sequence[str] = (),
    min_named_speakers: int = 1,
) -> list[Path]:
    from transcriptx.app.controllers.library_controller import LibraryController

    required = [n for n in require_named_speakers if str(n).strip()]
    min_named = max(1, int(min_named_speakers))
    backlog: list[Path] = []
    for meta in LibraryController().list_transcripts():
        path = Path(meta.path)
        if _has_completed_preset_run(path, analysis_preset):
            continue
        if require_complete_speakers and meta.speaker_map_status != "complete":
            continue
        if required and not _has_required_named_speakers(path, required):
            continue
        if _named_speaker_count(path) < min_named:
            continue
        backlog.append(path)
    backlog.sort(key=lambda p: str(p))
    return backlog


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    from transcriptx._bootstrap import bootstrap

    from transcriptx.core.config.persistence import apply_project_config_to_live_facade

    bootstrap()
    apply_project_config_to_live_facade()

    if args.llm_effort:
        _apply_llm_effort(str(args.llm_effort))

    required_names = list(args.require_named_speaker or [])
    min_named = max(1, int(args.min_named_speakers or 1))
    targets = _discover_backlog(
        analysis_preset=str(args.analysis_preset),
        require_complete_speakers=bool(args.require_complete_speakers),
        require_named_speakers=required_names,
        min_named_speakers=min_named,
    )
    if args.max and args.max > 0:
        targets = targets[: int(args.max)]

    named_note = (
        f", require_named_speakers={required_names!r}" if required_names else ""
    )
    effort_note = f", llm_effort={args.llm_effort!r}" if args.llm_effort else ""
    print(
        f"backlog: {len(targets)} transcript(s) "
        f"(preset={args.analysis_preset!r}"
        f", require_complete_speakers={bool(args.require_complete_speakers)}"
        f", min_named_speakers={min_named}"
        f"{named_note}{effort_note})"
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
