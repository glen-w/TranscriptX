#!/usr/bin/env python3
"""Assess / preprocess audio for transcription (helper script; not a GUI surface).

Not part of the core TranscriptX product path (import → analyze). Use when you
need to inspect or clean recordings before an external transcription tool.
Candidate for removal in 1.2 — see docs/ROADMAP.md.

Examples:
    uv run python scripts/audio_preprocess.py assess recording.wav
    uv run python scripts/audio_preprocess.py run recording.wav --mode auto
    uv run python scripts/audio_preprocess.py run recording.wav \\
        --mode selected --step denoise --step normalize -o ./out --format mp3
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from transcriptx.app.models.requests import PreprocessRequest  # noqa: E402
from transcriptx.app.workflows.preprocess import run_preprocess  # noqa: E402
from transcriptx.core.utils.config import get_config  # noqa: E402

# Decision keys accepted by apply_preprocessing / the former Audio Prep UI.
_KNOWN_STEPS = (
    "resample",
    "mono",
    "normalize",
    "denoise",
    "highpass",
    "lowpass",
    "bandpass",
)
_STEP_CONFIG_ATTRS = (
    "downsample",
    "convert_to_mono",
    "normalize_mode",
    "denoise_mode",
    "highpass_mode",
    "lowpass_mode",
    "bandpass_mode",
)


def _print_assessment(result) -> None:
    assessment = result.assessment or {}
    compliance = result.compliance
    print(f"noise_level: {assessment.get('noise_level', 'unknown')}")
    suggestions = assessment.get("suggested_steps") or []
    print(f"suggested_steps: {', '.join(suggestions) if suggestions else '(none)'}")
    if compliance is not None:
        print(f"compliance: {json.dumps(compliance, default=str)}")
    if assessment.get("details"):
        print(f"details: {json.dumps(assessment['details'], default=str)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Assess or preprocess audio before external transcription. "
            "Helper only — not a supported GUI or core product surface."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    assess = sub.add_parser("assess", help="Noise / compliance assessment only")
    assess.add_argument("input", type=Path, help="Input audio file")

    run = sub.add_parser("run", help="Preprocess (optionally assess first)")
    run.add_argument("input", type=Path, help="Input audio file")
    run.add_argument(
        "--mode",
        choices=("auto", "selected", "off"),
        default="auto",
        help="DSP mode (default: auto)",
    )
    run.add_argument(
        "--step",
        action="append",
        dest="steps",
        choices=_KNOWN_STEPS,
        default=None,
        help="Enable a step when --mode selected (repeatable)",
    )
    run.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: beside input)",
    )
    run.add_argument(
        "--format",
        choices=("wav", "mp3"),
        default="wav",
        dest="output_format",
        help="Output format (default: wav)",
    )
    run.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output",
    )
    run.add_argument(
        "--no-assess",
        action="store_true",
        help="Skip assessment phase (preprocess only)",
    )

    args = parser.parse_args(argv)

    if args.command == "assess":
        result = run_preprocess(
            PreprocessRequest(
                input_path=args.input.resolve(),
                operation="assess",
            )
        )
        if not result.success:
            for err in result.errors:
                print(f"error: {err}", file=sys.stderr)
            return 1
        _print_assessment(result)
        return 0

    if args.mode == "selected" and not args.steps:
        print(
            "error: --mode selected requires at least one --step",
            file=sys.stderr,
        )
        return 2

    decisions = None
    config = None
    if args.mode == "selected" and args.steps:
        decisions = {step: True for step in args.steps}
        # Honour --step by forcing per-step modes to "suggest".
        config = copy.deepcopy(get_config().audio_preprocessing)
        config.preprocessing_mode = "selected"
        for attr in _STEP_CONFIG_ATTRS:
            setattr(config, attr, "suggest")

    operation = "preprocess" if args.no_assess else "assess_and_preprocess"
    result = run_preprocess(
        PreprocessRequest(
            input_path=args.input.resolve(),
            operation=operation,
            preprocessing_mode=args.mode,
            output_dir=args.output_dir.resolve() if args.output_dir else None,
            output_format=args.output_format,
            overwrite=args.overwrite,
            preprocessing_decisions=decisions,
            config=config,
        )
    )
    if not result.success:
        for err in result.errors:
            print(f"error: {err}", file=sys.stderr)
        return 1

    if not args.no_assess:
        _print_assessment(result)
    if result.applied_steps:
        print(f"applied_steps: {', '.join(result.applied_steps)}")
    if result.output_path:
        print(f"output: {result.output_path}")
    for w in result.warnings:
        print(f"warning: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
