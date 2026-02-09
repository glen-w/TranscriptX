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

import contextlib
import json
import logging
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import questionary
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
from transcriptx.utils.spinner import SpinnerManager
import builtins

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

# Add diagnostics commands
app.add_typer(doctor_app, name="doctor", help="Diagnostics commands")
app.add_typer(audit_app, name="audit", help="Audit pipeline runs")

logger = get_logger()


@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context):
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


@contextlib.contextmanager
def _spinner_print_guard():
    """Patch print temporarily so it synchronizes with the spinner."""
    original_print = builtins.print

    def spinner_safe_print(*args, **kwargs):
        SpinnerManager.pause_spinner()
        try:
            original_print(*args, **kwargs)
        finally:
            SpinnerManager.resume_spinner()

    builtins.print = spinner_safe_print
    main_mod = sys.modules.get("__main__")
    had_spinner = main_mod is not None and hasattr(main_mod, "spinner_safe_print")
    old_spinner = getattr(main_mod, "spinner_safe_print", None) if main_mod else None
    if main_mod is not None:
        main_mod.spinner_safe_print = spinner_safe_print
    try:
        yield
    finally:
        builtins.print = original_print
        if main_mod is not None:
            if had_spinner:
                main_mod.spinner_safe_print = old_spinner
            else:
                try:
                    delattr(main_mod, "spinner_safe_print")
                except AttributeError:
                    pass


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
):
    """
    Main TranscriptX CLI with enhanced error handling and user feedback.

    This command provides an interactive interface for transcript analysis
    with comprehensive error handling, progress tracking, and graceful exit.
    """
    ensure_data_dirs()
    _configure_nltk_data_path()
    # When a subcommand is invoked (e.g. preprocess, process-wav convert), apply global options then let the subcommand run
    if ctx.invoked_subcommand is not None:
        if config_file and not hasattr(config_file, "default"):
            try:
                load_config(str(config_file))
            except Exception:
                pass
        if output_dir and not hasattr(output_dir, "default"):
            try:
                cfg = get_config()
                cfg.output.base_output_dir = str(output_dir)
            except Exception:
                pass
        return
    with graceful_exit():
        with _spinner_print_guard():
            _main_impl(config_file, log_level, output_dir)


def run_interactive():
    """Entry point for the interactive CLI."""
    ensure_data_dirs()
    _configure_nltk_data_path()
    with _spinner_print_guard():
        _main_impl()


def _initialize_whisperx_service():
    """
    Initialize WhisperX Docker Compose service on startup.
    This ensures the service is ready when the user wants to transcribe.
    Waits until container is confirmed ready before showing menu.
    """
    try:
        from .transcription_utils_compose import (
            check_whisperx_compose_service,
            start_whisperx_compose_service,
            wait_for_whisperx_service,
        )

        # Check if WhisperX service is already running and ready
        if check_whisperx_compose_service():
            # Verify it's actually ready with a test exec
            if wait_for_whisperx_service(timeout=5):
                logger.info(
                    "WhisperX Docker Compose service is already running and ready"
                )
                return True
            # Container exists but not ready, will start below

        # Try to start the service
        print("\n[cyan]🔧 Initializing WhisperX service...[/cyan]")
        logger.info("Starting WhisperX Docker Compose service on startup")

        if start_whisperx_compose_service():
            logger.info("WhisperX Docker Compose service started successfully")
            return True
        else:
            print(
                "[yellow]⚠️  WhisperX service could not be started. You can start it manually when needed.[/yellow]"
            )
            logger.warning("Failed to start WhisperX Docker Compose service on startup")
            return False

    except Exception as e:
        # Don't fail startup if WhisperX can't be started
        print(
            "[yellow]⚠️  Could not initialize WhisperX service. You can start it manually when needed.[/yellow]"
        )
        logger.warning(f"Error initializing WhisperX service: {e}", exc_info=True)
        return False


def _check_audio_playback_dependencies():
    """
    Check audio playback dependencies on startup.
    Informs user about available features (basic playback vs. seeking support).
    """
    import sys
    import shutil

    try:
        from .audio import check_ffplay_available

        # Check for ffplay (enables seeking support)
        ffplay_available, ffplay_error = check_ffplay_available()

        # Check for afplay (macOS built-in, basic playback only)
        is_macos = sys.platform == "darwin"
        afplay_available = is_macos and shutil.which("afplay") is not None

        if ffplay_available:
            logger.info(
                "Audio playback: ffplay available (full features including seeking)"
            )
            # Don't print anything - ffplay is available, all features work
        elif afplay_available:
            logger.info(
                "Audio playback: afplay available (basic playback only, no seeking)"
            )
            print(
                "[dim]ℹ️  Audio playback: Basic playback available. Install ffmpeg (ffplay) for skip forward/backward controls.[/dim]"
            )
        else:
            logger.warning("Audio playback: No playback tools available")
            print(
                "[yellow]⚠️  Audio playback: No playback tools found. Install ffmpeg (ffplay) for audio playback features.[/yellow]"
            )

    except Exception as e:
        # Don't fail startup if check fails
        logger.warning(
            f"Error checking audio playback dependencies: {e}", exc_info=True
        )


def _ensure_playwright_ready():
    """
    Ensure Playwright package and browser are ready for use.
    This proactively installs Playwright if needed, avoiding warnings during NER analysis.
    """
    try:
        from transcriptx.core.utils.lazy_imports import ensure_playwright_ready

        # Silently check and install if needed (only shows warnings on failure)
        if ensure_playwright_ready(silent=True):
            logger.info("Playwright: Ready for NER location map rendering")
        else:
            logger.debug("Playwright: Not available (NER location maps will be HTML-only)")
    except Exception as e:
        # Don't fail startup if check fails
        logger.debug(f"Playwright check skipped: {e}")


def _ensure_pdf_ready():
    """
    Ensure PDF dependencies (reportlab) are installed in the active venv.
    Lazy-loaded; installs on first use so summary all-charts PDF works when needed.
    """
    try:
        from transcriptx.core.utils.lazy_imports import ensure_pdf_ready

        if ensure_pdf_ready(silent=True):
            logger.debug("PDF deps: ready for summary charts")
        else:
            logger.debug("PDF deps: not available (summary all-charts PDF will be skipped)")
    except Exception as e:
        logger.debug(f"PDF deps check skipped: {e}")


def _check_and_install_streamlit(*, allow_install: bool = False) -> bool:
    """
    Check if Streamlit is available and install it if missing.
    Ensures the web interface is available.
    """
    try:
        # Directly check if streamlit can be imported
        try:
            import streamlit  # type: ignore  # noqa: F401

            logger.info("Streamlit is available for web interface")
            return True
        except ImportError:
            pass  # Streamlit not available, will try to install

        if not allow_install:
            print("[yellow]⚠️  Streamlit is not available.[/yellow]")
            print("[dim]Install manually with: pip install streamlit>=1.29.0[/dim]")
            logger.info("Streamlit missing; auto-install disabled in non-interactive mode")
            return False

        if not questionary.confirm(
            "Streamlit is not installed. Install it now?", default=False
        ).ask():
            print("[yellow]⚠️  Streamlit install skipped.[/yellow]")
            return False

        # Streamlit is not available, try to install it
        print("[cyan]📦 Installing Streamlit for web interface...[/cyan]")
        logger.info("Streamlit not available, attempting to install streamlit>=1.29.0")

        install_cmd = [sys.executable, "-m", "pip", "install", "streamlit>=1.29.0"]

        result = subprocess.run(
            install_cmd, capture_output=True, text=True, timeout=180  # 3 minute timeout
        )

        if result.returncode == 0:
            # Verify installation by trying to import
            try:
                import streamlit  # type: ignore  # noqa: F401

                print("[green]✅ Streamlit installed successfully[/green]")
                logger.info("Streamlit installed successfully")
                return True
            except ImportError:
                print(
                    "[yellow]⚠️  Streamlit installation completed but import failed. Please restart the application.[/yellow]"
                )
                logger.warning("Streamlit installation completed but import failed")
                return False
        else:
            print("[yellow]⚠️  Could not install Streamlit automatically.[/yellow]")
            print("[dim]Install manually with: pip install streamlit>=1.29.0[/dim]")

            if result.stderr:
                logger.warning(f"Streamlit installation failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("[yellow]⚠️  Streamlit installation timed out.[/yellow]")
        print("[dim]Install manually with: pip install streamlit>=1.29.0[/dim]")
        logger.warning("Streamlit installation timed out")
        return False
    except Exception as e:
        # Don't fail startup if installation fails
        print("[yellow]⚠️  Could not install Streamlit automatically.[/yellow]")
        print("[dim]Install manually with: pip install streamlit>=1.28.0[/dim]")
        logger.warning(f"Error checking/installing Streamlit: {e}", exc_info=True)
        return False


def _check_and_install_librosa(*, allow_install: bool = False) -> bool:
    """
    Check if librosa is available and install it if missing.
    Ensures content-based duplicate detection is available.

    On macOS, handles LLVM dependency issues for llvmlite (numba dependency).
    """
    try:
        # Directly check if librosa can be imported (more reliable than cached flag)
        try:
            import librosa  # type: ignore  # noqa: F401

            logger.info("librosa is available for content-based duplicate detection")
            return True
        except ImportError:
            pass  # librosa not available, will try to install

        if not allow_install:
            print("[yellow]⚠️  librosa is not available.[/yellow]")
            print("[dim]Install manually with: pip install librosa>=0.10.0[/dim]")
            logger.info("librosa missing; auto-install disabled in non-interactive mode")
            return False

        if not questionary.confirm(
            "librosa is not installed. Install it now?", default=False
        ).ask():
            print("[yellow]⚠️  librosa install skipped.[/yellow]")
            return False

        # librosa is not available, try to install it
        print(
            "[cyan]📦 Installing librosa for content-based duplicate detection...[/cyan]"
        )
        logger.info("librosa not available, attempting to install librosa>=0.10.0")

        # On macOS, prefer pre-built wheels to avoid LLVM build issues
        is_macos = sys.platform == "darwin"
        install_cmd = [sys.executable, "-m", "pip", "install"]

        if is_macos:
            # Try to use pre-built wheels first (avoids building llvmlite)
            install_cmd.extend(["--prefer-binary", "librosa>=0.10.0"])
        else:
            install_cmd.append("librosa>=0.10.0")

        result = subprocess.run(
            install_cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            # Verify installation by trying to import
            try:
                import librosa  # type: ignore  # noqa: F401

                print("[green]✅ librosa installed successfully[/green]")
                logger.info("librosa installed successfully")
                # Note: The audio_fingerprinting module's LIBROSA_AVAILABLE flag
                # won't update until module reload, but direct imports will work
                return True
            except ImportError:
                print(
                    "[yellow]⚠️  librosa installation completed but import failed. Please restart the application.[/yellow]"
                )
                logger.warning("librosa installation completed but import failed")
                return False
        else:
            # Installation failed - check if it's an LLVM/llvmlite issue on macOS
            error_output = result.stderr or result.stdout or ""
            is_llvm_error = (
                "llvmlite" in error_output.lower() or "llvm" in error_output.lower()
            )

            if is_macos and is_llvm_error:
                print(
                    "[yellow]⚠️  librosa installation failed due to LLVM dependency issue.[/yellow]"
                )
                print(
                    "[dim]On macOS, librosa requires LLVM to build llvmlite (numba dependency).[/dim]"
                )
                print("[dim]To fix this, install LLVM via Homebrew:[/dim]")
                print("[cyan]  brew install llvm[/cyan]")
                print("[dim]Then set environment variables and retry:[/dim]")
                print(
                    "[cyan]  export LLVM_CONFIG=$(brew --prefix llvm)/bin/llvm-config[/cyan]"
                )
                print("[cyan]  export CMAKE_PREFIX_PATH=$(brew --prefix llvm)[/cyan]")
                print("[cyan]  pip install librosa>=0.10.0[/cyan]")
                print(
                    "[dim]Or use pre-built wheels: pip install --only-binary :all: librosa>=0.10.0[/dim]"
                )
            else:
                print(
                    "[yellow]⚠️  Could not install librosa automatically. Using size-only duplicate detection.[/yellow]"
                )
                print("[dim]Install manually with: pip install librosa>=0.10.0[/dim]")

            if result.stderr:
                logger.warning(f"librosa installation failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print(
            "[yellow]⚠️  librosa installation timed out. Using size-only duplicate detection.[/yellow]"
        )
        print("[dim]Install manually with: pip install librosa>=0.10.0[/dim]")
        logger.warning("librosa installation timed out")
        return False
    except Exception as e:
        # Don't fail startup if installation fails
        print(
            "[yellow]⚠️  Could not install librosa automatically. Using size-only duplicate detection.[/yellow]"
        )
        print("[dim]Install manually with: pip install librosa>=0.10.0[/dim]")
        logger.warning(f"Error checking/installing librosa: {e}", exc_info=True)
        return False


def _show_preprocessing_menu() -> None:
    """Display and handle preprocessing submenu options."""
    while True:
        try:
            choice = questionary.select(
                "Preprocessing Options",
                choices=[
                    "🎵 Process WAV Files",
                    "🔧 Preprocess single audio file (MP3/WAV/...)",
                    "📄 Import VTT File",
                    "📄 Import SRT File",
                    "🔍 Find & Remove Duplicates",
                    "📝 Rename Files",
                    "⬅️ Back to main menu",
                ],
            ).ask()
        except KeyboardInterrupt:
            print("\n[cyan]Returning to main menu...[/cyan]")
            break

        if choice == "🎵 Process WAV Files":
            from .wav_processing_workflow import run_wav_processing_workflow

            run_wav_processing_workflow()
        elif choice == "🔧 Preprocess single audio file (MP3/WAV/...)":
            from .file_selection_utils import select_single_audio_file_for_preprocessing
            from .wav_processing_workflow import run_preprocess_single_file

            print("\n[bold cyan]🔧 Preprocess single audio file[/bold cyan]")
            print("[dim]Select an MP3, WAV, or other audio file to run preprocessing.[/dim]")
            file_path = select_single_audio_file_for_preprocessing()
            if not file_path:
                print("\n[yellow]No file selected. Returning to menu.[/yellow]")
                continue
            result = run_preprocess_single_file(file_path=file_path, skip_confirm=False)
            if result["status"] == "cancelled":
                print("\n[yellow]Cancelled.[/yellow]")
            elif result["status"] == "failed":
                print(f"\n[red]❌ {result['error']}[/red]")
            else:
                out_path = result["output_path"]
                steps = result.get("applied_steps") or []
                print(f"\n[green]✅ Saved to {out_path}[/green]")
                if steps:
                    print(f"   Applied: {', '.join(steps)}")
        elif choice == "📄 Import VTT File":
            from .vtt_import_workflow import run_vtt_import_workflow

            run_vtt_import_workflow()
        elif choice == "📄 Import SRT File":
            from .srt_import_workflow import run_srt_import_workflow

            run_srt_import_workflow()
        elif choice == "🔍 Find & Remove Duplicates":
            from .deduplication_workflow import run_deduplication_workflow

            run_deduplication_workflow()
        elif choice == "📝 Rename Files":
            from .file_rename_workflow import run_file_rename_workflow

            run_file_rename_workflow()
        elif choice == "⬅️ Back to main menu":
            break


def _show_transcribe_menu() -> None:
    """Display and handle transcribe submenu options."""
    while True:
        try:
            choice = questionary.select(
                "Transcribe Options",
                choices=[
                    "🎤 WhisperX",
                    "⬅️ Back to main menu",
                ],
            ).ask()
        except KeyboardInterrupt:
            print("\n[cyan]Returning to main menu...[/cyan]")
            break

        if choice == "🎤 WhisperX":
            from .transcription_workflow import run_transcription_workflow

            run_transcription_workflow()
        elif choice == "⬅️ Back to main menu":
            break


def _find_streamlit_app() -> Path | None:
    """Find the Streamlit app.py file using multiple fallback methods."""
    # Method 0 (preferred): Resolve via the imported module location.
    # This is robust to running from arbitrary working directories.
    try:
        from importlib import import_module

        module = import_module("transcriptx.web.app")
        module_file = getattr(module, "__file__", None)
        if module_file:
            candidate = Path(module_file)
            if candidate.exists():
                return candidate
    except Exception:
        # Fall back to filesystem heuristics below.
        pass

    # Method 1: Calculate from __file__ location (4 levels up from src/transcriptx/cli/main.py)
    project_root = Path(__file__).parent.parent.parent.parent
    streamlit_app = project_root / "src" / "transcriptx" / "web" / "app.py"
    if streamlit_app.exists():
        return streamlit_app

    # Method 2: Try relative to current working directory
    cwd_app = Path.cwd() / "src" / "transcriptx" / "web" / "app.py"
    if cwd_app.exists():
        return cwd_app

    # Method 3: Try using the package location
    try:
        import transcriptx

        package_path = Path(transcriptx.__file__).parent
        package_app = package_path / "web" / "app.py"
        if package_app.exists():
            return package_app
    except (ImportError, AttributeError):
        pass

    # Method 4: Search from current directory up to find project root
    current = Path.cwd()
    for _ in range(5):  # Search up to 5 levels
        test_app = current / "src" / "transcriptx" / "web" / "app.py"
        if test_app.exists():
            return test_app
        if current == current.parent:  # Reached filesystem root
            break
        current = current.parent

    return None


def _show_browser_menu() -> None:
    """Launch the Streamlit web interface in the browser."""
    host = "127.0.0.1"
    port = 8501  # Streamlit default port
    url = f"http://{host}:{port}"

    try:
        # Check and install Streamlit if needed
        if not _check_and_install_streamlit(allow_install=True):
            print("[yellow]⚠️  Streamlit is required for the web interface.[/yellow]")
            print(
                "[dim]Please install it manually with: pip install streamlit>=1.29.0[/dim]"
            )
            return

        # Get the path to the Streamlit app
        streamlit_app = _find_streamlit_app()

        if streamlit_app is None:
            print("[red]Streamlit app not found at: src/transcriptx/web/app.py[/red]")
            print(
                "[yellow]Please ensure you're running from the project root directory.[/yellow]"
            )
            return

        # Launch Streamlit in subprocess
        print(f"[green]Starting Streamlit web interface on {url}[/green]")
        print(f"[cyan]Opening browser...[/cyan]")

        # Start Streamlit process
        process = subprocess.Popen(
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
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait a moment for server to start
        time.sleep(2)

        # Open browser
        webbrowser.open(url)
        print(f"[green]✓ Web interface opened in your browser[/green]")
        print(
            f"[dim]Note: Keep this CLI session open to keep the server running.[/dim]"
        )
        print(
            f"[dim]Press Enter to stop the server and return to the main menu...[/dim]"
        )

        # Wait for user to press Enter
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            # Terminate the Streamlit process
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                process.kill()

    except FileNotFoundError:
        log_error(
            "CLI",
            "Streamlit not found. Please install it with: pip install streamlit",
            exception=None,
        )
        print(
            f"[red]Streamlit not found. Please install it with: pip install streamlit[/red]"
        )
    except Exception as e:
        log_error("CLI", f"Failed to start web viewer: {e}", exception=e)
        print(f"[red]Failed to start web viewer: {e}[/red]")
        print(
            f"[yellow]You can also start it manually with: transcriptx web-viewer[/yellow]"
        )


def _get_docker_compose_command() -> list[str] | None:
    """Return docker compose command as argv list (v1 or v2)."""
    try:
        subprocess.run(
            ["docker-compose", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return ["docker-compose"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    try:
        subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return ["docker", "compose"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _guess_lan_ip() -> str:
    """Best-effort LAN IP guess for printing a connect URL."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't need to be reachable; connect() just selects an outbound interface.
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip:
                return ip
        finally:
            sock.close()
    except Exception:
        pass
    return "127.0.0.1"


def _show_interface_menu() -> None:
    """Interface submenu: Streamlit browser UI (expandable later)."""
    while True:
        try:
            choice = questionary.select(
                "Interface Options",
                choices=[
                    "🌐 Browser (Streamlit)",
                    "⬅️ Back to main menu",
                ],
            ).ask()
        except KeyboardInterrupt:
            print("\n[cyan]Returning to main menu...[/cyan]")
            return

        if choice in (None, "⬅️ Back to main menu"):
            return
        if choice == "🌐 Browser (Streamlit)":
            _show_browser_menu()


def _main_impl(
    config_file: Path | None = None,
    log_level: str | None = None,
    output_dir: Path | None = None,
):
    """
    🎤 TranscriptX - Advanced Transcript Analysis Toolkit

    Interactive transcript analysis with speaker diarization, sentiment analysis,
    emotion detection, NER, and more.
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

    # Ensure optional deps available (install into venv if missing); lazy-loaded when used
    _ensure_pdf_ready()

    # Show banner
    show_banner()

    # Note: Side-effect functions moved to lazy initialization:
    # - WhisperX service: initialized in transcribe_with_whisperx() when transcription needed
    # - Audio playback: checked in play_audio_file() when playback needed
    # - librosa: checked/installed in deduplication_workflow when duplicate detection needed
    # - Streamlit: checked/installed in _show_browser_menu() when web interface needed

    while True:
        try:
            # Main menu with arrow selection
            choice = questionary.select(
                "What would you like to do?",
                choices=[
                    "🔧 Preprocessing",
                    "🎤 Transcribe",
                    "🗣️  Manage Speakers",
                    "👥 Groups",
                    "✏️  Post-processing",
                    "📊 Analyze",
                    "🧪 Test Analysis",
                    "🗄️  Batch Process",
                    "🧭 Interface",
                    "⚙️  Settings",
                    "🚪 Exit",
                ],
            ).ask()
        except KeyboardInterrupt:
            print("\n[green]👋 Thanks for using TranscriptX! Exiting.[/green]")
            logger.info("User exited TranscriptX via Ctrl+C at main menu")
            exit_user_cancel()

        if choice == "🔧 Preprocessing":
            _show_preprocessing_menu()

        elif choice == "🎤 Transcribe":
            _show_transcribe_menu()

        elif choice == "📊 Analyze":
            from .analysis_workflow import run_single_analysis_workflow

            run_single_analysis_workflow()

        elif choice == "✏️  Post-processing":
            from .post_processing_workflow import _show_post_processing_menu

            _show_post_processing_menu()

        elif choice == "🧪 Test Analysis":
            from .analysis_workflow import run_test_analysis_workflow

            run_test_analysis_workflow()

        elif choice == "🗣️  Manage Speakers":
            from .speaker_management import _show_speaker_management_menu

            _show_speaker_management_menu()

        elif choice == "👥 Groups":
            from .group_management import _show_group_management_menu

            _show_group_management_menu()

        elif choice == "🗄️  Batch Process":
            from .batch_wav_workflow import run_batch_wav_workflow

            run_batch_wav_workflow()

        elif choice == "🧭 Interface":
            _show_interface_menu()

        elif choice == "⚙️  Settings":
            from transcriptx.cli.config_editor import edit_config_interactive

            edit_config_interactive()

        elif choice == "🚪 Exit":
            print("\n[green]👋 Thanks for using TranscriptX![/green]")
            logger.info("User exited TranscriptX")
            exit_success()


@app.command("web-viewer")
def web_viewer(
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8501, help="Port to run on (Streamlit default: 8501)"),
):
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
            f"[red]Streamlit not found. Please install it with: pip install streamlit[/red]"
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
):
    """
    Analyze a transcript file with specified modules and settings.
    """
    from .analysis_workflow import run_analysis_non_interactive
    from .analysis_utils import apply_analysis_mode_settings_non_interactive
    from .workflow_utils import set_non_interactive_mode
    from transcriptx.core.pipeline.module_registry import get_default_modules
    from transcriptx.core.pipeline.run_options import SpeakerRunOptions
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

    try:
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

        result = run_analysis_non_interactive(  # type: ignore[call-arg]
            transcript_file=transcript_file,
            mode=mode,
            modules=module_list,
            profile=profile,
            skip_confirm=skip_confirm,
            output_dir=output_dir,
            speaker_options=speaker_options,
            persist=persist,
        )

        if result.get("status") == "cancelled":
            exit_user_cancel()
        elif result.get("status") == "failed":
            exit_error("Analysis failed")
    except (FileNotFoundError, ValueError) as e:
        print(f"[red]❌ Error: {e}[/red]")
        raise CliExit.error(str(e))


@app.command()
def transcribe(
    audio_file: Path = typer.Option(..., "--audio-file", "-a", help="Path to audio file"),
    engine: str = typer.Option(
        "auto",
        "--engine",
        help="Transcription engine: auto or whisperx",
    ),
    analyze: bool = typer.Option(
        False, "--analyze", help="Run analysis after transcription"
    ),
    analysis_mode: str = typer.Option(
        "quick",
        "--analysis-mode",
        "-m",
        help="Analysis mode if --analyze is set: quick or full",
    ),
    analysis_modules: str = typer.Option(
        "all",
        "--analysis-modules",
        help="Comma-separated list of modules for analysis or 'all'",
    ),
    skip_confirm: bool = typer.Option(
        False, "--skip-confirm", help="Skip confirmation prompts"
    ),
    print_output_json_path: bool = typer.Option(
        False,
        "--print-output-json-path",
        "--json-path-only",
        help="Print only the transcript JSON path to stdout",
    ),
):
    """
    Transcribe an audio file using WhisperX.
    """
    from .transcription_workflow import run_transcription_non_interactive

    # Parse analysis modules
    if analyze:
        if analysis_modules.lower() == "all":
            module_list = None
        else:
            module_list = [m.strip() for m in analysis_modules.split(",") if m.strip()]
    else:
        module_list = None

    try:
        if print_output_json_path:
            logger = get_logger()
            handler_streams: list[tuple[logging.Handler, object]] = []
            for handler in logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler_streams.append((handler, handler.stream))
                    handler.setStream(sys.stderr)
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    result = run_transcription_non_interactive(
                        audio_file=audio_file,
                        engine=engine,
                        analyze=analyze,
                        analysis_mode=analysis_mode,
                        analysis_modules=module_list,
                        skip_confirm=skip_confirm,
                    )
            finally:
                for handler, stream in handler_streams:
                    handler.setStream(stream)
            status = result.get("status")
            if status == "completed" and result.get("transcript_file"):
                print(result["transcript_file"])
                return
            if status == "cancelled":
                print("Transcription cancelled.", file=sys.stderr)
                raise CliExit.user_cancel()
            error_msg = result.get("error") or "Transcription failed"
            print(error_msg, file=sys.stderr)
            raise CliExit.error()
        else:
            result = run_transcription_non_interactive(
                audio_file=audio_file,
                engine=engine,
                analyze=analyze,
                analysis_mode=analysis_mode,
                analysis_modules=module_list,
                skip_confirm=skip_confirm,
            )

            if result.get("status") == "cancelled":
                exit_user_cancel()
            elif result.get("status") == "failed":
                exit_error(result.get("error") or "Transcription failed")
    except (FileNotFoundError, ValueError) as e:
        print(f"[red]❌ Error: {e}[/red]")
        raise CliExit.error(str(e))


@app.command("identify-speakers")
def identify_speakers(
    transcript_file: Path = typer.Option(..., "--transcript-file", "-t", help="Path to transcript JSON file"),
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
):
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
process_wav_app = typer.Typer(help="Process WAV files: convert, merge, or compress")
app.add_typer(process_wav_app, name="process-wav")


@process_wav_app.command("convert")
def process_wav_convert(
    files: str = typer.Option(
        ..., "--files", "-f", help="Comma-separated list of WAV file paths"
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
):
    """
    Convert WAV files to MP3.
    """
    from .wav_processing_workflow import run_wav_convert_non_interactive

    # Parse file paths
    file_paths = [Path(f.strip()) for f in files.split(",") if f.strip()]

    try:
        result = run_wav_convert_non_interactive(
            files=file_paths,
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
        help="Comma-separated list of WAV file paths in merge order (minimum 2)",
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
):
    """
    Merge multiple WAV files into one MP3 file.
    """
    from .wav_processing_workflow import run_wav_merge_non_interactive

    # Parse file paths
    file_paths = [Path(f.strip()) for f in files.split(",") if f.strip()]

    try:
        result = run_wav_merge_non_interactive(
            files=file_paths,
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
    file: Path = typer.Option(..., "--file", "-f", help="Path to audio file (MP3, WAV, etc.)"),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output path (default: same dir, stem_preprocessed.<ext>)"
    ),
    skip_confirm: bool = typer.Option(
        False, "--skip-confirm", help="Skip confirmation if output exists"
    ),
):
    """
    Run audio preprocessing on a single file (MP3, WAV, or other supported format).

    Applies denoise, normalize, filters, mono/resample according to your config.
    For steps in "suggest" mode, assesses the file and applies suggested steps.
    """
    from .wav_processing_workflow import run_preprocess_single_file

    suffix = file.suffix.lower()
    if suffix not in (".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"):
        print(f"[yellow]⚠️  Unusual extension {suffix}; pydub may still support it.[/yellow]")

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
):
    """
    Compress WAV files in backups directory into zip archives.
    """
    from .wav_processing_workflow import run_wav_compress_non_interactive

    try:
        result = run_wav_compress_non_interactive(
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


@app.command("batch-process")
def batch_process(
    folder: Path = typer.Option(..., "--folder", help="Path to folder containing WAV files"),
    size_filter: str = typer.Option(
        "all",
        "--size-filter",
        help="Filter by size: all, small (<30MB), or large (≥30MB)",
    ),
    files: str | None = typer.Option(
        None, "--files", "-f", help="Comma-separated list of specific files to process"
    ),
    resume: bool = typer.Option(
        False, "--resume", help="Resume from checkpoint if available"
    ),
    clear_checkpoint: bool = typer.Option(
        False, "--clear-checkpoint", help="Clear existing checkpoint before processing"
    ),
    move_wavs: bool = typer.Option(
        False, "--move-wavs", help="Move WAV files to storage after processing"
    ),
    identify_speakers: bool = typer.Option(
        False, "--identify-speakers", help="Run speaker identification after processing"
    ),
    analyze: bool = typer.Option(
        False, "--analyze", help="Run analysis pipeline after processing"
    ),
    analysis_mode: str = typer.Option(
        "quick", "--analysis-mode", help="Analysis mode if --analyze is set"
    ),
    skip_confirm: bool = typer.Option(
        False, "--skip-confirm", help="Skip confirmation prompts"
    ),
):
    """
    Batch process WAV files: convert, transcribe, detect type, and extract tags.
    """
    from .batch_wav_workflow import run_batch_process_non_interactive

    # Parse files if provided
    file_paths = None
    if files:
        file_paths = [Path(f.strip()) for f in files.split(",") if f.strip()]

    try:
        result = run_batch_process_non_interactive(
            folder=folder,
            size_filter=size_filter,
            files=file_paths,
            resume=resume,
            clear_checkpoint=clear_checkpoint,
            move_wavs=move_wavs,
            identify_speakers=identify_speakers,
            analyze=analyze,
            analysis_mode=analysis_mode,
            skip_confirm=skip_confirm,
        )

        if result.get("status") == "cancelled":
            exit_user_cancel()
        elif result.get("status") == "failed":
            exit_error("Operation failed")
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"[red]❌ Error: {e}[/red]")
        raise CliExit.error(str(e))


@app.command()
def deduplicate(
    folder: Path = typer.Option(..., "--folder", help="Path to folder to scan for duplicates"),
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
):
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
        ..., "--output-file", "-o", help="Path to output simplified transcript JSON file"
    ),
    tics_file: Path | None = typer.Option(
        None, help="Path to JSON file with list of tics/hesitations"
    ),
    agreements_file: Path | None = typer.Option(
        None, help="Path to JSON file with list of agreement phrases"
    ),
):
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
):
    """Launch the interactive menu (default when run with no arguments)."""
    with graceful_exit():
        ensure_data_dirs()
        _configure_nltk_data_path()
        with _spinner_print_guard():
            _main_impl(config_file, log_level, output_dir)


@app.command("settings")
def settings_cmd(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    edit: bool = typer.Option(False, "--edit", help="Open interactive config editor"),
    save: bool = typer.Option(False, "--save", help="Save configuration"),
):
    """Manage settings via flags (show/edit/save)."""
    from transcriptx.cli.config_editor import (
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
):
    """Run test analysis via flags (non-interactive)."""
    from .analysis_workflow import run_analysis_non_interactive, run_test_analysis_workflow

    if transcript_file is None:
        run_test_analysis_workflow()
        return

    module_list = None if modules.lower() == "all" else [
        m.strip() for m in modules.split(",") if m.strip()
    ]
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
    action: str = typer.Option(
        "start", "--action", help="Action: start or stop"
    ),
    open_browser: bool = typer.Option(
        False, "--open-browser", help="Open local URL in browser after start"
    ),
):
    """Manage WhisperX Web GUI stack via flags."""
    project_root = Path(__file__).parent.parent.parent.parent
    compose_file = project_root / "examples" / "docker-compose.ui-whisperx.yml"
    if not compose_file.exists():
        print(
            f"[red]Compose file not found: {compose_file}[/red]\n"
            "[yellow]Expected: examples/docker-compose.ui-whisperx.yml[/yellow]"
        )
        raise typer.Exit(1)

    compose_cmd = _get_docker_compose_command()
    if compose_cmd is None:
        print(
            "[red]Docker Compose not found.[/red]\n"
            "[dim]Install Docker Desktop (includes docker compose) or docker-compose v1.[/dim]"
        )
        raise typer.Exit(1)

    action = action.lower().strip()
    if action not in {"start", "stop"}:
        print("[red]Invalid --action. Use 'start' or 'stop'.[/red]")
        raise typer.Exit(1)

    try:
        if action == "stop":
            cmd = [
                *compose_cmd,
                "-f",
                str(compose_file),
                "--profile",
                "whisperx",
                "--profile",
                "ui",
                "down",
            ]
            result = subprocess.run(
                cmd, cwd=str(project_root), capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                print("[green]✅ WhisperX Web GUI stack stopped[/green]")
            else:
                print("[red]❌ Failed to stop stack[/red]")
                if result.stderr:
                    print(f"[dim]{result.stderr.strip()}[/dim]")
            return

        cmd = [
            *compose_cmd,
            "-f",
            str(compose_file),
            "--profile",
            "whisperx",
            "--profile",
            "ui",
            "up",
            "-d",
            "whisperx",
            "ui",
        ]
        print("[cyan]Starting WhisperX Web GUI stack in background...[/cyan]")
        result = subprocess.run(
            cmd, cwd=str(project_root), capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            print("[red]❌ Failed to start stack[/red]")
            if result.stderr:
                print(f"[dim]{result.stderr.strip()}[/dim]")
            return

        port = 7860
        local_url = f"http://127.0.0.1:{port}"
        lan_url = f"http://{_guess_lan_ip()}:{port}"

        print("[green]✅ WhisperX Web GUI stack started[/green]")
        print(f"[cyan]Local:[/cyan] {local_url}")
        print(f"[cyan]LAN:[/cyan]   {lan_url}")

        if open_browser:
            webbrowser.open(local_url)
    except Exception as e:
        log_error("CLI", f"Failed to manage WhisperX Web GUI stack: {e}", exception=e)
        print(f"[red]Failed to manage WhisperX Web GUI stack: {e}[/red]")
        raise typer.Exit(1)


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
