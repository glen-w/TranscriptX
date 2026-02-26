"""Audio preprocessing workflow (single file and batch)."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from rich import print

from transcriptx.cli.audio import (
    apply_preprocessing,
    assess_audio_noise,
    check_audio_compliance,
)
from transcriptx.cli.file_selection_utils import AUDIO_EXTENSIONS
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.paths import PREPROCESSING_DIR, WAV_STORAGE_DIR

from . import (
    check_ffmpeg_available,
    get_wav_folder_start_path,
    questionary,
    select_audio_files_interactive,
)

from . import (
    collect_audio_file_infos,
    create_audio_progress,
    print_audio_file_list,
    run_workflow_safely,
)

logger = get_logger()


def run_preprocess_single_file(
    file_path: Path,
    output_path: Path | None = None,
    skip_confirm: bool = False,
) -> Dict[str, Any]:
    """
    Run audio preprocessing on a single file (MP3, WAV, or other supported format).

    Args:
        file_path: Path to the audio file.
        output_path: Optional output path. Default: same dir, stem_preprocessed.<ext>.
        skip_confirm: If True, overwrite existing output without asking.

    Returns:
        Dict with status ("ok" | "cancelled" | "failed"), output_path, applied_steps, error.
    """
    result: Dict[str, Any] = {
        "status": "ok",
        "output_path": None,
        "applied_steps": [],
        "error": None,
    }

    file_path = file_path.resolve()
    if not file_path.exists():
        result["status"] = "failed"
        result["error"] = f"File not found: {file_path}"
        return result

    try:
        from pydub import AudioSegment
    except ImportError:
        result["status"] = "failed"
        result["error"] = "pydub is not installed. Install with: pip install pydub"
        return result

    ffmpeg_ok, err = check_ffmpeg_available()
    if not ffmpeg_ok:
        result["status"] = "failed"
        result["error"] = err
        return result

    config = get_config().audio_preprocessing
    suffix = file_path.suffix.lower()
    if output_path is None:
        output_path = file_path.parent / f"{file_path.stem}_preprocessed{suffix}"
    else:
        output_path = output_path.resolve()

    if output_path.exists() and not skip_confirm:
        ok = questionary.confirm(f"Overwrite {output_path.name}?", default=False).ask()
        if not ok:
            result["status"] = "cancelled"
            return result

    print(f"[bold]Loading[/bold] {file_path.name}...")
    try:
        audio = AudioSegment.from_file(str(file_path))
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        return result

    preprocessing_decisions = None
    needs_suggest = (
        config.preprocessing_mode == "suggest"
        or config.denoise_mode == "suggest"
        or config.highpass_mode == "suggest"
        or config.lowpass_mode == "suggest"
        or config.bandpass_mode == "suggest"
        or config.normalize_mode == "suggest"
        or config.convert_to_mono == "suggest"
        or config.downsample == "suggest"
    )
    if needs_suggest:
        print("[dim]Assessing audio...[/dim]")
        assessment = assess_audio_noise(file_path)
        preprocessing_decisions = {
            "denoise": "denoise" in assessment["suggested_steps"],
            "highpass": "highpass" in assessment["suggested_steps"],
            "lowpass": "lowpass" in assessment["suggested_steps"],
            "bandpass": "bandpass" in assessment["suggested_steps"],
            "normalize": "normalize" in assessment["suggested_steps"],
            "mono": "mono" in assessment["suggested_steps"],
            "resample": "resample" in assessment["suggested_steps"],
        }

    print("[bold]Applying preprocessing...[/bold]")
    try:
        processed_audio, applied_steps = apply_preprocessing(
            audio,
            config,
            progress_callback=None,
            preprocessing_decisions=preprocessing_decisions,
        )
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        return result

    out_ext = output_path.suffix.lower()
    fmt = (
        "mp3"
        if out_ext == ".mp3"
        else "wav" if out_ext == ".wav" else out_ext.lstrip(".")
    )
    if fmt == "mp3":
        processed_audio.export(str(output_path), format="mp3", bitrate="192k")
    else:
        processed_audio.export(str(output_path), format=fmt)

    result["output_path"] = output_path
    result["applied_steps"] = applied_steps
    return result


def _run_preprocessing_workflow() -> None:
    """Run the audio preprocessing workflow."""

    def _body() -> None:
        try:
            from pydub import AudioSegment
        except ImportError:
            print(
                "\n[red]❌ pydub is not installed. Please install it to use preprocessing features.[/red]"
            )
            return

        print("\n[bold cyan]〰️ Audio Preprocessing[/bold cyan]")
        print(
            "[dim]Optimize audio files for transcription with ASR-safe preprocessing[/dim]"
        )

        ffmpeg_available, error_msg = check_ffmpeg_available()
        if not ffmpeg_available:
            print(f"\n[red]❌ {error_msg}[/red]")
            print(
                "[yellow]Please install ffmpeg to use preprocessing features.[/yellow]"
            )
            return

        config = get_config()
        audio_config = config.audio_preprocessing

        print("\n[dim]Select audio files to preprocess[/dim]")
        start_path = get_wav_folder_start_path(config)
        audio_files = select_audio_files_interactive(
            start_path=start_path, extensions=AUDIO_EXTENSIONS
        )
        if not audio_files:
            print("\n[yellow]⚠️ No audio files selected. Returning to menu.[/yellow]")
            return

        infos = collect_audio_file_infos(audio_files)
        print_audio_file_list(infos)

        print("\n[bold]Assessing audio files...[/bold]")
        assessments = []
        skipped_files = []

        with create_audio_progress(show_pct=False) as progress:
            task = progress.add_task("Assessing files...", total=len(audio_files))

            for af in audio_files:
                progress.update(task, description=f"Assessing {af.name}...")

                compliance = check_audio_compliance(af, audio_config)
                if (
                    compliance["is_compliant"]
                    and audio_config.skip_if_already_compliant
                ):
                    skipped_files.append((af, "already compliant"))
                    progress.advance(task)
                    continue

                assessment = assess_audio_noise(af)
                assessments.append((af, assessment, compliance))
                progress.advance(task)

        if skipped_files:
            print(
                f"\n[yellow]⚠️ Skipped {len(skipped_files)} file(s) (already compliant):[/yellow]"
            )
            for af, reason in skipped_files:
                print(f"  • {af.name} ({reason})")

        if not assessments:
            print(
                "\n[cyan]All files are already compliant. No preprocessing needed.[/cyan]"
            )
            return

        print("\n[bold]Assessment Results:[/bold]")
        print("-" * 80)
        for af, assessment, compliance in assessments:
            noise_level = assessment["noise_level"]
            noise_emoji = (
                "🟢"
                if noise_level == "low"
                else "🟡" if noise_level == "medium" else "🔴"
            )
            print(f"\n{noise_emoji} {af.name}")
            print(
                f"  Noise Level: {noise_level.upper()} (confidence: {assessment['confidence']:.1%})"
            )
            if assessment["suggested_steps"]:
                print(f"  Suggested Steps: {', '.join(assessment['suggested_steps'])}")
            if compliance["missing_requirements"]:
                print(f"  Missing: {', '.join(compliance['missing_requirements'])}")

        if not questionary.confirm(
            f"\nPreprocess {len(assessments)} file(s) with suggested settings?"
        ).ask():
            print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
            return

        print("\n[bold]Applying preprocessing...[/bold]")
        processed_files = []
        failed_files = []

        with create_audio_progress(show_pct=False) as progress:
            task = progress.add_task("Processing files...", total=len(assessments))

            for af, assessment, compliance in assessments:
                try:
                    progress.update(task, description=f"Processing {af.name}...")

                    audio = AudioSegment.from_file(str(af))

                    preprocessing_decisions: Dict[str, bool] = {
                        "denoise": "denoise" in assessment["suggested_steps"],
                        "highpass": "highpass" in assessment["suggested_steps"],
                        "lowpass": "lowpass" in assessment["suggested_steps"],
                        "bandpass": "bandpass" in assessment["suggested_steps"],
                        "normalize": "normalize" in assessment["suggested_steps"],
                        "mono": "mono" in assessment["suggested_steps"],
                        "resample": "resample" in assessment["suggested_steps"],
                    }

                    processed_audio, applied_steps = apply_preprocessing(
                        audio, audio_config, None, preprocessing_decisions
                    )

                    original_path = af
                    original_file_size_mb = original_path.stat().st_size / (1024 * 1024)
                    suffix = af.suffix.lower()

                    backup_dir = Path(WAV_STORAGE_DIR)
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    original_backup_path = backup_dir / f"{af.stem}_original{suffix}"

                    counter = 1
                    while original_backup_path.exists():
                        original_backup_path = (
                            backup_dir / f"{af.stem}_original_{counter}{suffix}"
                        )
                        counter += 1

                    shutil.move(str(original_path), str(original_backup_path))

                    out_fmt = (
                        "mp3"
                        if suffix == ".mp3"
                        else "wav" if suffix == ".wav" else suffix.lstrip(".")
                    )
                    if out_fmt == "mp3":
                        processed_audio.export(
                            str(original_path), format="mp3", bitrate="192k"
                        )
                    else:
                        processed_audio.export(str(original_path), format=out_fmt)

                    processed_file_size_mb = original_path.stat().st_size / (
                        1024 * 1024
                    )

                    preprocessing_dir = Path(PREPROCESSING_DIR)
                    preprocessing_dir.mkdir(parents=True, exist_ok=True)
                    sidecar_path = preprocessing_dir / f"{af.stem}_preprocessing.json"
                    sidecar_data = {
                        "original_file": str(original_backup_path),
                        "processed_file": str(original_path),
                        "assessment": {
                            "noise_level": assessment["noise_level"],
                            "confidence": assessment["confidence"],
                            "suggested_steps": assessment["suggested_steps"],
                            "metrics": assessment["metrics"],
                        },
                        "applied_steps": applied_steps,
                        "before": {
                            "file_size_mb": original_file_size_mb,
                            "channels": audio.channels,
                            "sample_rate": audio.frame_rate,
                        },
                        "after": {
                            "file_size_mb": processed_file_size_mb,
                            "channels": processed_audio.channels,
                            "sample_rate": processed_audio.frame_rate,
                        },
                        "timestamp": datetime.now().isoformat(),
                    }

                    with open(sidecar_path, "w") as f:
                        json.dump(sidecar_data, f, indent=2)

                    processed_files.append((af, applied_steps))
                    progress.advance(task)

                except Exception as e:
                    logger.error(f"Error preprocessing {af}: {e}")
                    log_error(
                        "AUDIO_PREPROCESSING",
                        f"Failed to preprocess {af}: {e}",
                        exception=e,
                    )
                    failed_files.append((af, str(e)))
                    progress.advance(task)

        print("\n" + "=" * 80)
        print("[bold green]✅ Preprocessing Complete[/bold green]")
        print("=" * 80)

        if processed_files:
            print(
                f"\n[green]Successfully processed {len(processed_files)} file(s):[/green]"
            )
            for af, steps in processed_files:
                print(f"  • {af.name}")
                if steps:
                    print(f"    Applied: {', '.join(steps)}")
                print(
                    f"    Original moved to: data/backups/wav/{af.stem}_original{af.suffix}"
                )
                print(
                    f"    Metadata saved as: data/preprocessing/{af.stem}_preprocessing.json"
                )

        if failed_files:
            print(f"\n[red]Failed to process {len(failed_files)} file(s):[/red]")
            for af, error in failed_files:
                print(f"  • {af.name}: {error}")

    if run_workflow_safely("AUDIO_PREPROCESSING", _body, interactive=True) is not None:
        return
