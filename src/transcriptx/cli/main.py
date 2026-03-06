"""
Modern Typer-based CLI for TranscriptX.

This module provides a comprehensive command-line interface for TranscriptX using
the Typer library. It offers both interactive and non-interactive modes for
transcript analysis, with features including:

- Interactive file and folder selection
- Module selection with dependency handling
- Configuration management
- Audio transcription
- Batch processing capabilities
- Progress tracking and user feedback

The CLI is designed to be user-friendly while providing access to all of
TranscriptX's advanced features. It includes intelligent defaults and
helpful prompts to guide users through the analysis process.

Key Features:
- Interactive folder navigation for file selection
- Smart module selection with dependency resolution
- Configuration editing with validation
- Audio transcription with model selection
- Batch processing for multiple files
- Real-time progress tracking
- Comprehensive error handling and user feedback

Usage Patterns:
1. Interactive mode: Run without arguments for guided setup
2. Non-interactive mode: Use command-line arguments for automation
3. Configuration mode: Edit settings without running analysis
"""

# Suppress CPR warning from prompt_toolkit when terminal doesn't support it (e.g. Docker attach)
import os

os.environ.setdefault("PROMPT_TOOLKIT_NO_CPR", "1")

# Load .env before any app modules that compute path constants
from transcriptx._bootstrap import bootstrap

bootstrap()

import json
import subprocess
import sys
from pathlib import Path

import typer
from rich import print

# Import core TranscriptX functionality
from transcriptx.core.utils.config import load_config, get_config
from transcriptx.core.config.persistence import get_project_config_path
from transcriptx.core.utils.logger import get_logger, setup_logging, log_error
from transcriptx.core.analysis.simplified_transcript import TranscriptSimplifier
from transcriptx.core.utils.paths import ensure_data_dirs

# Import enhanced error handling
from transcriptx.utils.error_handling import graceful_exit

# Import standardized exit codes
from .exit_codes import (
    CliExit,
    EXIT_USER_CANCEL,
    exit_success,
    exit_error,
    exit_user_cancel,
)

# Import CLI utilities
from .display_utils import show_banner
from .interactive_menu import (
    _check_and_install_streamlit,
    _find_streamlit_app,
    run_interactive_menu,
)

# Import database commands
from .database_commands import app as database_app

# Import cross-session commands
from .cross_session_commands import app as cross_session_app

# Import transcript commands
from .transcript_commands import app as transcript_app

# Import artifact commands
from .artifact_commands import app as artifact_app
from .group_commands import app as group_app
from .perf_commands import app as perf_app
from .analysis_commands import app as analysis_app
from .deps_commands import app as deps_app
from .diagnostics_commands import doctor_app, audit_app

# Initialize the Typer application
# Typer provides a modern CLI framework with automatic help generation
# and rich text formatting capabilities
app = typer.Typer(
    name="transcriptx",
    help="🎤 TranscriptX - Advanced Transcript Analysis Toolkit",
    add_completion=False,
    rich_markup_mode="rich",  # Enable rich text formatting in help and output
)

# Add database commands as a subcommand
app.add_typer(database_app, name="database", help="Database management commands")

# Add cross-session commands as a subcommand
app.add_typer(
    cross_session_app,
    name="cross-session",
    help="Cross-session speaker tracking commands",
)

# Add transcript commands as a subcommand
app.add_typer(transcript_app, name="transcript", help="Transcript management commands")

# Add artifact commands as a subcommand
app.add_typer(artifact_app, name="artifacts", help="Artifact validation commands")

# Add group commands as a subcommand
app.add_typer(group_app, name="group", help="TranscriptSet group commands")

# Add performance commands as a subcommand
app.add_typer(perf_app, name="perf", help="Performance span queries")
app.add_typer(analysis_app, name="analysis", help="Analysis commands")
app.add_typer(
    deps_app, name="deps", help="Optional dependency status and install (extras)"
)

# Add diagnostics commands
app.add_typer(doctor_app, name="doctor", help="Diagnostics commands")
app.add_typer(audit_app, name="audit", help="Audit pipeline runs")

logger = get_logger()


@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context) -> None:
    """🎤 TranscriptX - Advanced Transcript Analysis Toolkit"""
    if ctx.invoked_subcommand is None:
        # No subcommand was invoked, run the interactive menu
        main()


def _configure_nltk_data_path() -> None:
    """Ensure NLTK can find the project's nltk_data directory."""
    try:
        import nltk

        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        nltk_data_dir = project_root / "nltk_data"
        if nltk_data_dir.exists():
            nltk.data.path.insert(0, str(nltk_data_dir))
    except ImportError:
        # NLTK not installed, skip configuration
        return
    except Exception:
        # If there's any issue configuring NLTK, continue anyway
        return


def main(
    ctx: typer.Context,
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    log_level: str | None = typer.Option(
        None,
        "--log-level",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Custom output directory",
    ),
    core: bool | None = typer.Option(
        None,
        "--core",
        help="Force core mode (only core modules, no auto-install of optional deps)",
    ),
    no_core: bool | None = typer.Option(
        None,
        "--no-core",
        help="Disable core mode (all modules, allow auto-install)",
    ),
) -> None:
    """
    Main TranscriptX CLI with enhanced error handling and user feedback.

    This command provides an interactive interface for transcript analysis
    with comprehensive error handling, progress tracking, and graceful exit.
    """
    ensure_data_dirs()
    _configure_nltk_data_path()
    # Resolve config (CLI > env > config file > install marker)
    if config_file and not hasattr(config_file, "default"):
        try:
            load_config(str(config_file))
        except Exception as e:
            logger.warning("Could not load config file %s: %s", config_file, e)
    cfg = get_config()
    if core is True:
        cfg.core_mode = True
    if no_core is True:
        cfg.core_mode = False
    if output_dir and not hasattr(output_dir, "default"):
        try:
            cfg.output.base_output_dir = str(output_dir)
        except Exception as e:
            logger.warning("Could not set output dir %s: %s", output_dir, e)
    # When a subcommand is invoked (e.g. preprocess, process-wav convert), apply global options then let the subcommand run
    if ctx.invoked_subcommand is not None:
        return
    from .startup import _spinner_print_guard

    with graceful_exit():
        with _spinner_print_guard():
            _run_interactive_setup_and_menu(config_file, log_level, output_dir)


def run_interactive() -> None:
    """Entry point for the interactive CLI."""
    ensure_data_dirs()
    _configure_nltk_data_path()
    from .startup import _spinner_print_guard

    with _spinner_print_guard():
        _run_interactive_setup_and_menu()


# Alias for tests and code that mock the main entry
_main_impl = main

# Re-export startup helpers for tests and any code that imports from main
from .startup import (
    _check_audio_playback_dependencies,
    _ensure_pdf_ready,
    _ensure_playwright_ready,
    _spinner_print_guard,
)


def run_startup_checks() -> None:
    """Run startup checks in order. Implementations live in startup.py."""
    _check_audio_playback_dependencies()
    _ensure_playwright_ready()
    _ensure_pdf_ready()


def _run_interactive_setup_and_menu(
    config_file: Path | None = None,
    log_level: str | None = None,
    output_dir: Path | None = None,
) -> None:
    """
    Load config, set up logging, run startup checks, then run the interactive menu.
    Menu implementation lives in interactive_menu.run_interactive_menu().
    """
    # Setup logging - handle OptionInfo objects properly
    if log_level is None or hasattr(log_level, "default"):
        log_level = "DEBUG"
    else:
        log_level = str(log_level)
    setup_logging(level=log_level)

    # Load configuration - handle OptionInfo objects properly
    if config_file and not hasattr(config_file, "default"):
        try:
            load_config(str(config_file))
            logger.info(f"Loaded configuration from {config_file}")
        except Exception as e:
            log_error(
                "CLI",
                f"Failed to load configuration from {config_file}: {e}",
                exception=e,
            )
            print(f"[red]Failed to load configuration: {e}[/red]")
            raise CliExit.config_error(f"Failed to load configuration: {e}")
    else:
        # Load project config by default so .transcriptx/config.json is used (e.g. Hugging Face token)
        project_config_path = get_project_config_path()
        if project_config_path.exists():
            try:
                load_config(str(project_config_path))
                logger.info(f"Loaded configuration from {project_config_path}")
            except Exception:
                pass  # fall back to defaults + env

    # Update output directory if specified
    if output_dir and not hasattr(output_dir, "default"):
        config = get_config()
        config.output.base_output_dir = str(output_dir)
        logger.info(f"Updated output directory to: {output_dir}")

    run_startup_checks()

    show_banner()
    run_interactive_menu()


@app.command("gui")
def gui(
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8501, help="Port to run on (Streamlit default: 8501)"),
) -> None:
    """Launch the integrated Streamlit GUI (primary interactive experience)"""
    web_viewer(host=host, port=port)


@app.command("web-viewer")
def web_viewer(
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8501, help="Port to run on (Streamlit default: 8501)"),
) -> None:
    """Launch the Streamlit web viewer interface"""
    try:
        # Check and install Streamlit if needed
        if not _check_and_install_streamlit(allow_install=False):
            print("[yellow]⚠️  Streamlit is required for the web interface.[/yellow]")
            print(
                "[dim]Please install it manually with: pip install streamlit>=1.29.0[/dim]"
            )
            raise CliExit.error(
                "Streamlit is required but could not be installed automatically"
            )

        # Get the path to the Streamlit app
        streamlit_app = _find_streamlit_app()

        if streamlit_app is None:
            error_msg = "Streamlit app not found at: src/transcriptx/web/app.py"
            print(f"[red]{error_msg}[/red]")
            print(
                "[yellow]Please ensure you're running from the project root directory.[/yellow]"
            )
            raise CliExit.error(error_msg)

        logger.info(f"Starting Streamlit web viewer on http://{host}:{port}")
        print(f"[green]Starting Streamlit web viewer on http://{host}:{port}[/green]")
        print(f"[cyan]Open your browser and navigate to: http://{host}:{port}[/cyan]")

        # Launch Streamlit
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(streamlit_app),
                "--server.port",
                str(port),
                "--server.address",
                host,
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ]
        )
    except FileNotFoundError:
        log_error(
            "CLI",
            "Streamlit not found. Please install it with: pip install streamlit",
            exception=None,
        )
        print(
            "[red]Streamlit not found. Please install it with: pip install streamlit[/red]"
        )
        raise CliExit.error(
            "Streamlit not found. Please install it with: pip install streamlit"
        )
    except Exception as e:
        log_error("CLI", f"Failed to start web viewer: {e}", exception=e)
        print(f"[red]Failed to start web viewer: {e}[/red]")
        raise CliExit.error(f"Failed to start web viewer: {e}")


@app.command()
def analyze(
    transcript_file: Path | None = typer.Option(
        None, "--transcript-file", "-t", help="Path to transcript JSON file"
    ),
    transcripts: list[Path] | None = typer.Option(
        None,
        "--transcripts",
        help="Analyze multiple transcripts as a group (repeat flag for each file)",
    ),
    all_transcripts: bool = typer.Option(
        False,
        "--all-transcripts",
        help="Analyze all available transcript JSON files",
    ),
    mode: str = typer.Option(
        "quick", "--mode", "-m", help="Analysis mode: quick or full"
    ),
    modules: str = typer.Option(
        "all", "--modules", help="Comma-separated list of modules or 'all'"
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Semantic profile for full mode: balanced, academic, business, casual, technical, interview",
    ),
    skip_confirm: bool = typer.Option(
        False, "--skip-confirm", help="Skip confirmation prompts"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Custom output directory"
    ),
    include_unidentified_speakers: bool = typer.Option(
        False,
        "--include-unidentified-speakers",
        help="Include unidentified speakers in per-speaker outputs",
    ),
    anonymise_speakers: bool = typer.Option(
        False,
        "--anonymise-speakers",
        help="Anonymise speaker display names in outputs",
    ),
    skip_speaker_identification: bool = typer.Option(
        False,
        "--skip-speaker-identification",
        help="Skip the speaker identification gate",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Run in non-interactive mode (skip all prompts)",
    ),
    persist: bool = typer.Option(
        False, "--persist", help="Persist run metadata and artifacts to DB"
    ),
    manifest: Path | None = typer.Option(
        None,
        "--manifest",
        help="Load run input from a RunManifestInput JSON file (overrides -t and module/speaker flags)",
    ),
    accept_noncanonical: bool = typer.Option(
        False,
        "--accept-noncanonical",
        help="Allow analyzing transcript files that do not use the canonical filename (*_transcriptx.json). Use only when the file is already in TranscriptX schema.",
    ),
) -> None:
    """
    Analyze a transcript file with specified modules and settings.
    """
    from .analysis_utils import apply_analysis_mode_settings_non_interactive
    from .workflow_utils import set_non_interactive_mode
    from transcriptx.core.pipeline.module_registry import get_default_modules
    from transcriptx.core.pipeline.run_options import SpeakerRunOptions
    from transcriptx.core.utils.path_utils import is_canonical_transcript_filename
    from transcriptx.cli.batch_workflows import run_batch_analysis_pipeline
    from transcriptx.cli.file_selection_utils import discover_all_transcript_paths

    if all_transcripts and (transcript_file is not None or transcripts):
        raise CliExit.error(
            "--all-transcripts cannot be combined with --transcript-file or --transcripts"
        )

    # Set non-interactive mode if requested
    if non_interactive:
        set_non_interactive_mode(True)

    # Parse modules
    if modules.lower() == "all":
        module_list = None
    else:
        module_list = [m.strip() for m in modules.split(",") if m.strip()]

    speaker_options = SpeakerRunOptions(
        include_unidentified=include_unidentified_speakers,
        anonymise=anonymise_speakers,
        skip_identification=skip_speaker_identification,
    )

    def _check_canonical(path: Path, accept: bool) -> None:
        if accept:
            return
        if not is_canonical_transcript_filename(path):
            raise CliExit.error(
                f"Transcript file does not use the canonical filename: {path.name}\n"
                "Canonical files must end with *_transcriptx.json (or *_canonical.json for migration).\n"
                "Run: transcriptx transcript canonicalize --in <file>  or pass --accept-noncanonical to analyze this file anyway."
            )

    def _maybe_hint_raw_whisperx(path: Path) -> None:
        """If input is loadable but not canonical (no schema_version), print a one-line hint to stderr."""
        try:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, dict) and "schema_version" in data:
                return
            from transcriptx.io.transcript_loader import normalize_segments

            segments = normalize_segments(data)
            if segments:
                print(
                    "[info] Input is raw WhisperX JSON (loadable). Tip: transcriptx transcript canonicalize --in <file> for canonical metadata.",
                    file=sys.stderr,
                )
        except (OSError, json.JSONDecodeError, Exception):
            pass

    try:
        # Canonical pipeline entry from manifest file
        if manifest is not None:
            from transcriptx.core.pipeline.run_schema import RunManifestInput
            from transcriptx.core import run_analysis_pipeline

            m = RunManifestInput.from_file(manifest)
            result = run_analysis_pipeline(manifest=m)
            if result.get("status") == "failed" or result.get("errors"):
                exit_error("Analysis failed")
            return
        if all_transcripts:
            discovered = discover_all_transcript_paths()
            if not discovered:
                raise CliExit.error(
                    "No transcript files found in configured transcript folders."
                )
            transcripts = discovered

        if transcripts:
            ordered = list(transcripts)
            if transcript_file is not None:
                ordered.insert(0, transcript_file)
            for p in ordered:
                _check_canonical(
                    Path(p) if isinstance(p, str) else p, accept_noncanonical
                )
            apply_analysis_mode_settings_non_interactive(mode, profile)
            selected_modules = (
                get_default_modules([str(path) for path in ordered])
                if module_list is None
                else module_list
            )
            run_batch_analysis_pipeline(
                [str(path) for path in ordered],
                analysis_mode=mode,
                selected_modules=selected_modules,
                skip_speaker_gate=speaker_options.skip_identification,
                speaker_options=speaker_options,
                persist=persist,
            )
            return

        if transcript_file is None:
            raise CliExit.error("Missing transcript file or --transcripts list")

        _check_canonical(transcript_file, accept_noncanonical)
        _maybe_hint_raw_whisperx(transcript_file)

        if not skip_confirm:
            from rich.prompt import Confirm
            if not Confirm.ask("Proceed with analysis?"):
                exit_user_cancel()

        from transcriptx.app.controllers.analysis_controller import AnalysisController
        from transcriptx.app.models.requests import AnalysisRequest

        request = AnalysisRequest(
            transcript_path=transcript_file,
            mode=mode,
            modules=module_list,
            profile=profile,
            skip_speaker_mapping=speaker_options.skip_identification,
            output_dir=output_dir,
            persist=persist,
            include_unidentified_speakers=speaker_options.include_unidentified,
        )
        controller = AnalysisController()
        result = controller.run_analysis(request)

        if result.status == "cancelled":
            exit_user_cancel()
        elif not result.success:
            if result.errors:
                for err in result.errors:
                    print(f"[yellow]  • {err}[/yellow]")
            exit_error("Analysis failed")

        if result.run_dir:
            print(f"Output directory: {result.run_dir}")
    except (FileNotFoundError, ValueError) as e:
        print(f"[red]❌ Error: {e}[/red]")
        raise CliExit.error(str(e))


@app.command()
def transcribe(
    audio_file: Path = typer.Option(
        None, "--audio-file", "-a", help="Path to audio file"
    ),
    engine: str = typer.Option("auto", "--engine", help="(Deprecated)"),
    analyze: bool = typer.Option(False, "--analyze", help="(Deprecated)"),
    analysis_mode: str = typer.Option(
        "quick", "--analysis-mode", "-m", help="(Deprecated)"
    ),
    analysis_modules: str = typer.Option(
        "all", "--analysis-modules", help="(Deprecated)"
    ),
    skip_confirm: bool = typer.Option(False, "--skip-confirm", help="(Deprecated)"),
    print_output_json_path: bool = typer.Option(
        False, "--print-output-json-path", "--json-path-only", help="(Deprecated)"
    ),
) -> None:
    """
    [DEPRECATED] TranscriptX no longer transcribes audio directly. See docs/transcription.md.
    """
    print(
        "ERROR: command deprecated\n\n"
        "[DEPRECATED] TranscriptX no longer transcribes audio directly.\n"
        "This command will be removed in v0.2.\n\n"
        "To generate a compatible transcript:\n"
        "  1. See: docs/transcription.md\n"
        "  2. If you already have WhisperX JSON:\n"
        "     transcriptx transcript canonicalize --in whisperx.json --out transcriptx.json\n"
        "  3. Then analyze:\n"
        "     transcriptx analyze --transcript-file transcriptx.json\n",
        file=sys.stderr,
    )
    raise typer.Exit(2)


@app.command("identify-speakers")
def identify_speakers(
    transcript_file: Path = typer.Option(
        ..., "--transcript-file", "-t", help="Path to transcript JSON file"
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing speaker identification without confirmation",
    ),
    skip_rename: bool = typer.Option(
        False,
        "--skip-rename",
        help="Skip transcript rename after speaker identification",
    ),
) -> None:
    """
    Identify speakers in a transcript file.
    """
    from .speaker_workflow import run_speaker_identification_non_interactive

    try:
        result = run_speaker_identification_non_interactive(
            transcript_file=transcript_file,
            overwrite=overwrite,
            skip_rename=skip_rename,
        )

        if result.get("status") == "cancelled":
            exit_user_cancel()
        elif result.get("status") == "failed":
            exit_error("Analysis failed")
    except (FileNotFoundError, ValueError) as e:
        print(f"[red]❌ Error: {e}[/red]")
        raise CliExit.error(str(e))


# Create process-wav command group
process_wav_app = typer.Typer(
    help="Process audio files: convert, merge, or compress (WAV, MP3, OGG, etc.)"
)
app.add_typer(process_wav_app, name="process-wav")


@process_wav_app.command("convert")
def process_wav_convert(
    files: str = typer.Option(
        ...,
        "--files",
        "-f",
        help="Comma-separated list of audio file paths (WAV, MP3, OGG, etc.)",
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Output directory for MP3 files"
    ),
    move_wavs: bool = typer.Option(
        False, "--move-wavs", help="Move original WAV files to storage after conversion"
    ),
    auto_rename: bool = typer.Option(
        True,
        "--auto-rename/--no-auto-rename",
        help="Automatically rename MP3 files after conversion",
    ),
    skip_confirm: bool = typer.Option(
        False, "--skip-confirm", help="Skip confirmation prompts"
    ),
) -> None:
    """
    Convert audio files (WAV, MP3, OGG, etc.) to MP3.
    """
    from .commands.wav import do_wav_convert

    file_paths = [Path(f.strip()) for f in files.split(",") if f.strip()]
    try:
        result = do_wav_convert(
            file_paths=file_paths,
            output_dir=output_dir,
            move_wavs=move_wavs,
            auto_rename=auto_rename,
            skip_confirm=skip_confirm,
        )
        if result.get("status") == "cancelled":
            exit_user_cancel()
        elif result.get("status") == "failed":
            exit_error("Operation failed")
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"[red]❌ Error: {e}[/red]")
        raise CliExit.error(str(e))


@process_wav_app.command("merge")
def process_wav_merge(
    files: str = typer.Option(
        ...,
        "--files",
        "-f",
        help="Comma-separated list of audio file paths (WAV, MP3, OGG, etc.) in merge order (minimum 2)",
    ),
    output_file: str | None = typer.Option(
        None, "--output-file", "-o", help="Output MP3 filename"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Output directory"
    ),
    backup_wavs: bool = typer.Option(
        True,
        "--backup-wavs/--no-backup-wavs",
        help="Backup WAV files to storage before merging",
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Overwrite output file if it exists"
    ),
    skip_confirm: bool = typer.Option(
        False, "--skip-confirm", help="Skip confirmation prompts"
    ),
) -> None:
    """
    Merge multiple audio files (WAV, MP3, OGG, etc.) into one MP3 file.
    """
    from .commands.wav import do_wav_merge

    file_paths = [Path(f.strip()) for f in files.split(",") if f.strip()]
    try:
        result = do_wav_merge(
            file_paths=file_paths,
            output_file=output_file,
            output_dir=output_dir,
            backup_wavs=backup_wavs,
            overwrite=overwrite,
            skip_confirm=skip_confirm,
        )
        if result.get("status") == "cancelled":
            exit_user_cancel()
        elif result.get("status") == "failed":
            exit_error("Operation failed")
    except (FileNotFoundError, ValueError, RuntimeError, FileExistsError) as e:
        print(f"[red]❌ Error: {e}[/red]")
        raise CliExit.error(str(e))


@app.command("preprocess")
def preprocess_audio(
    file: Path = typer.Option(
        ..., "--file", "-f", help="Path to audio file (MP3, WAV, etc.)"
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path (default: same dir, stem_preprocessed.<ext>)",
    ),
    skip_confirm: bool = typer.Option(
        False, "--skip-confirm", help="Skip confirmation if output exists"
    ),
) -> None:
    """
    Run audio preprocessing on a single file (MP3, WAV, or other supported format).

    Applies denoise, normalize, filters, mono/resample according to your config.
    For steps in "suggest" mode, assesses the file and applies suggested steps.
    """
    from .wav_processing_workflow import run_preprocess_single_file

    suffix = file.suffix.lower()
    if suffix not in (".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"):
        print(
            f"[yellow]⚠️  Unusual extension {suffix}; pydub may still support it.[/yellow]"
        )

    result = run_preprocess_single_file(
        file_path=file, output_path=output, skip_confirm=skip_confirm
    )

    if result["status"] == "cancelled":
        print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)
    if result["status"] == "failed":
        print(f"[red]❌ {result['error']}[/red]")
        raise typer.Exit(1)

    out_path = result["output_path"]
    steps = result.get("applied_steps") or []
    print(f"[green]✅ Saved to {out_path}[/green]")
    if steps:
        print(f"   Applied: {', '.join(steps)}")


@process_wav_app.command("compress")
def process_wav_compress(
    delete_originals: bool = typer.Option(
        False,
        "--delete-originals",
        help="Delete original WAV files after successful compression",
    ),
    storage_dir: Path | None = typer.Option(
        None, "--storage-dir", help="Custom WAV storage directory path"
    ),
    skip_confirm: bool = typer.Option(
        False, "--skip-confirm", help="Skip confirmation prompts"
    ),
) -> None:
    """
    Compress WAV files in backups directory into zip archives.
    """
    from .commands.wav import do_wav_compress

    try:
        result = do_wav_compress(
            delete_originals=delete_originals,
            storage_dir=storage_dir,
            skip_confirm=skip_confirm,
        )
        if result.get("status") == "cancelled":
            exit_user_cancel()
        elif result.get("status") == "failed":
            exit_error("Operation failed")
    except (FileNotFoundError, RuntimeError) as e:
        print(f"[red]❌ Error: {e}[/red]")
        raise CliExit.error(str(e))


@app.command("prep-audio")
def prep_audio(
    folder: Path = typer.Option(
        ...,
        "--folder",
        help="Path to folder containing audio files (WAV, MP3, OGG, etc.)",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory for converted files (default: same as input folder)",
    ),
) -> None:
    """
    Batch audio preparation: convert and normalize audio files to MP3. No transcription.
    """
    from .prep_audio_workflow import run_prep_audio_non_interactive

    try:
        result = run_prep_audio_non_interactive(folder=folder, output_dir=output_dir)
        if result.get("status") == "failed":
            exit_error(result.get("error", "Prep audio failed"))
    except (FileNotFoundError, ValueError) as e:
        print(f"[red]❌ Error: {e}[/red]")
        raise CliExit.error(str(e))


@app.command("batch-analyze")
def batch_analyze(
    folder: Path = typer.Option(
        None,
        "--folder",
        help="Path to folder containing transcript JSON files",
    ),
    manifest: Path | None = typer.Option(
        None,
        "--manifest",
        help="Load run input from a RunManifestInput JSON file (overrides --folder and module flags)",
    ),
    analysis_mode: str = typer.Option(
        "quick", "--analysis-mode", "-m", help="Analysis mode: quick or full"
    ),
    modules: str = typer.Option(
        "all", "--modules", help="Comma-separated list of modules or 'all'"
    ),
    skip_confirm: bool = typer.Option(
        False, "--skip-confirm", help="Skip confirmation prompts"
    ),
) -> None:
    """
    Bulk analysis on existing transcript JSON files in a folder.
    """
    from .batch_analyze_workflow import run_batch_analyze_non_interactive
    from transcriptx.core.pipeline.run_schema import RunManifestInput
    from transcriptx.core.pipeline.run_options import SpeakerRunOptions
    from transcriptx.core import run_analysis_pipeline
    from .batch_workflows import run_batch_analysis_pipeline

    if manifest is not None:
        m = RunManifestInput.from_file(manifest)
        manifest_path = Path(m.transcript_path)
        if manifest_path.is_dir():
            discovered = [p for p in manifest_path.rglob("*.json") if p.is_file()]
            if not discovered:
                raise CliExit.error(
                    f"No transcript JSON files found under {m.transcript_path}"
                )
            run_batch_analysis_pipeline(
                [str(p) for p in discovered],
                analysis_mode=m.mode,
                selected_modules=m.modules if m.modules != ["all"] else None,
                skip_speaker_gate=m.skip_speaker_gate,
                speaker_options=SpeakerRunOptions(
                    include_unidentified=m.include_unidentified_speakers
                ),
                persist=m.persist,
            )
        else:
            result = run_analysis_pipeline(manifest=m)
            if result.get("errors"):
                exit_error("Analysis failed")
        return

    if folder is None:
        raise CliExit.error("Either --folder or --manifest is required")
    module_list = (
        None
        if modules.lower() == "all"
        else [m.strip() for m in modules.split(",") if m.strip()]
    )
    try:
        result = run_batch_analyze_non_interactive(
            folder=folder,
            analysis_mode=analysis_mode,
            selected_modules=module_list,
            skip_confirm=skip_confirm,
        )
        if result.get("status") == "failed":
            exit_error(result.get("error", "Batch analyze failed"))
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"[red]❌ Error: {e}[/red]")
        raise CliExit.error(str(e))


@app.command()
def deduplicate(
    folder: Path = typer.Option(
        ..., "--folder", help="Path to folder to scan for duplicates"
    ),
    files: str | None = typer.Option(
        None, "--files", "-f", help="Comma-separated list of specific files to delete"
    ),
    auto_delete: bool = typer.Option(
        False,
        "--auto-delete",
        help="Automatically delete duplicates without interactive review (requires --files)",
    ),
    skip_confirm: bool = typer.Option(
        False,
        "--skip-confirm",
        help="Skip confirmation prompts (only used with --auto-delete)",
    ),
) -> None:
    """
    Find and remove duplicate files in a folder.
    """
    from .deduplication_workflow import run_deduplicate_non_interactive

    # Parse files if provided
    file_paths = None
    if files:
        file_paths = [Path(f.strip()) for f in files.split(",") if f.strip()]

    try:
        result = run_deduplicate_non_interactive(
            folder=folder,
            files=file_paths,
            auto_delete=auto_delete,
            skip_confirm=skip_confirm,
        )

        if result.get("status") == "cancelled":
            exit_user_cancel()
        elif result.get("status") == "requires_interaction":
            print(
                "\n[yellow]⚠️ Interactive review required. Run without --auto-delete to review duplicates interactively.[/yellow]"
            )
            exit_success()
    except (FileNotFoundError, ValueError) as e:
        print(f"[red]❌ Error: {e}[/red]")
        raise CliExit.error(str(e))


@app.command()
def simplify_transcript(
    input_file: Path = typer.Option(
        ...,
        "--input-file",
        "-i",
        help="Path to input transcript JSON file (list of dicts with 'speaker' and 'text')",
    ),
    output_file: Path = typer.Option(
        ...,
        "--output-file",
        "-o",
        help="Path to output simplified transcript JSON file",
    ),
    tics_file: Path | None = typer.Option(
        None, help="Path to JSON file with list of tics/hesitations"
    ),
    agreements_file: Path | None = typer.Option(
        None, help="Path to JSON file with list of agreement phrases"
    ),
) -> None:
    """
    Simplify a transcript by removing tics, hesitations, repetitions, and agreements, focusing on substantive content and decision points, while maintaining conversational flow.
    """
    # Load transcript
    with open(input_file) as f:
        transcript = json.load(f)
    # Load tics and agreements
    if tics_file:
        with open(tics_file) as f:
            tics = json.load(f)
    else:
        tics = ["um", "uh", "like", "you know", "I mean"]
    if agreements_file:
        with open(agreements_file) as f:
            agreements = json.load(f)
    else:
        agreements = ["yeah", "right", "absolutely", "I agree", "sure"]
    # Simplify
    simplifier = TranscriptSimplifier(tics, agreements)
    simplified = simplifier.simplify(transcript)
    # Write output
    with open(output_file, "w") as f:
        json.dump(simplified, f, indent=2)
    print(f"[green]✅ Simplified transcript written to {output_file}[/green]")


# Interactive menu: run when no subcommand is given (script passes "interactive" when no args)
@app.command("interactive")
def interactive_cmd(
    config_file: Path | None = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
    log_level: str | None = typer.Option(
        None, "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Custom output directory"
    ),
) -> None:
    """Launch the interactive menu (default when run with no arguments)."""
    with graceful_exit():
        ensure_data_dirs()
        _configure_nltk_data_path()
        with _spinner_print_guard():
            _run_interactive_setup_and_menu(config_file, log_level, output_dir)


@app.command("settings")
def settings_cmd(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    edit: bool = typer.Option(False, "--edit", help="Open interactive config editor"),
    save: bool = typer.Option(False, "--save", help="Save configuration"),
) -> None:
    """Manage settings via flags (show/edit/save)."""
    from transcriptx.cli.config_editor import (  # type: ignore[import-untyped]
        edit_config_interactive,
        show_current_config,
        save_config_interactive,
    )

    config = get_config()
    if show:
        show_current_config(config)
    if edit:
        edit_config_interactive()
    if save:
        save_config_interactive(config)
    if not (show or edit or save):
        edit_config_interactive()


@app.command("test-analysis")
def test_analysis_cmd(
    transcript_file: Path | None = typer.Option(
        None, "--transcript", "-t", help="Path to transcript JSON file"
    ),
    mode: str = typer.Option(
        "quick", "--mode", "-m", help="Analysis mode: quick or full"
    ),
    modules: str = typer.Option(
        "all", "--modules", help="Comma-separated list of modules or 'all'"
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Semantic profile for full mode",
    ),
    skip_confirm: bool = typer.Option(
        True, "--skip-confirm", help="Skip confirmation prompts"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Custom output directory"
    ),
) -> None:
    """Run test analysis via flags (non-interactive)."""
    from .analysis_workflow import (
        run_analysis_non_interactive,
        run_test_analysis_workflow,
    )

    if transcript_file is None:
        run_test_analysis_workflow()
        return

    module_list = (
        None
        if modules.lower() == "all"
        else [m.strip() for m in modules.split(",") if m.strip()]
    )
    run_analysis_non_interactive(
        transcript_file=transcript_file,
        mode=mode,
        modules=module_list,
        profile=profile,
        skip_confirm=skip_confirm,
        output_dir=output_dir,
        persist=False,
    )


@app.command("whisperx-web-gui")
def whisperx_web_gui_cmd(
    action: str = typer.Option("start", "--action", help="(Deprecated)"),
    open_browser: bool = typer.Option(False, "--open-browser", help="(Deprecated)"),
) -> None:
    """[DEPRECATED] TranscriptX no longer ships WhisperX Web GUI. See docs/transcription.md."""
    print(
        "ERROR: command deprecated\n\n"
        "[DEPRECATED] This command will be removed in v0.2.\n"
        "See docs/transcription.md for external transcription options.\n",
        file=sys.stderr,
    )
    raise typer.Exit(2)


# Make the main menu the default when no subcommand is given
app.callback()(main)


if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        print("\n[green]👋 Thanks for using TranscriptX! Exiting.[/green]")
        sys.exit(EXIT_USER_CANCEL)
    except typer.Exit as e:
        # Handle typer.Exit (including CliExit) gracefully without traceback
        sys.exit(e.exit_code)
