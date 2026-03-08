"""
Interactive main menu for TranscriptX CLI.

This module holds the menu loop and all submenus (preprocessing, interface, etc.)
so that main.py stays a thin entry point and command registration layer.
"""

from __future__ import annotations

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import questionary
from rich import print

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger, log_error

from .exit_codes import exit_success, exit_user_cancel

logger = get_logger()


def _check_and_install_streamlit(*, allow_install: bool = False) -> bool:
    """Check if Streamlit is available and install it if missing."""
    try:
        try:
            result = subprocess.run(
                [sys.executable, "-c", "import streamlit"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.info("Streamlit is available for web interface")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        if not allow_install:
            print("[yellow]⚠️  Streamlit is not available.[/yellow]")
            print("[dim]Install manually with: pip install streamlit>=1.29.0[/dim]")
            logger.info(
                "Streamlit missing; auto-install disabled in non-interactive mode"
            )
            return False

        if not questionary.confirm(
            "Streamlit is not installed. Install it now?", default=False
        ).ask():
            print("[yellow]⚠️  Streamlit install skipped.[/yellow]")
            return False

        print("[cyan]📦 Installing Streamlit for web interface...[/cyan]")
        logger.info("Streamlit not available, attempting to install streamlit>=1.29.0")
        install_cmd = [sys.executable, "-m", "pip", "install", "streamlit>=1.29.0"]
        result = subprocess.run(
            install_cmd,
            capture_output=True,
            text=True,
            timeout=180,
        )

        if result.returncode == 0:
            verify = subprocess.run(
                [sys.executable, "-c", "import streamlit"],
                capture_output=True,
                timeout=10,
            )
            if verify.returncode == 0:
                print("[green]✅ Streamlit installed successfully[/green]")
                logger.info("Streamlit installed successfully")
                return True
            print(
                "[yellow]⚠️  Streamlit installation completed but import failed. Please restart the application.[/yellow]"
            )
            logger.warning("Streamlit installation completed but import failed")
            return False
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
        print("[yellow]⚠️  Could not install Streamlit automatically.[/yellow]")
        print("[dim]Install manually with: pip install streamlit>=1.28.0[/dim]")
        logger.warning(f"Error checking/installing Streamlit: {e}", exc_info=True)
        return False


def _check_and_install_librosa(*, allow_install: bool = False) -> bool:
    """Check if librosa is available and install it if missing."""
    try:
        try:
            import librosa  # noqa: F401

            logger.info("librosa is available for content-based duplicate detection")
            return True
        except ImportError:
            pass

        if not allow_install:
            print("[yellow]⚠️  librosa is not available.[/yellow]")
            print("[dim]Install manually with: pip install librosa>=0.10.0[/dim]")
            logger.info(
                "librosa missing; auto-install disabled in non-interactive mode"
            )
            return False

        if not questionary.confirm(
            "librosa is not installed. Install it now?", default=False
        ).ask():
            print("[yellow]⚠️  librosa install skipped.[/yellow]")
            return False

        print(
            "[cyan]📦 Installing librosa for content-based duplicate detection...[/cyan]"
        )
        logger.info("librosa not available, attempting to install librosa>=0.10.0")
        is_macos = sys.platform == "darwin"
        install_cmd = [sys.executable, "-m", "pip", "install"]
        if is_macos:
            install_cmd.extend(["--prefer-binary", "librosa>=0.10.0"])
        else:
            install_cmd.append("librosa>=0.10.0")

        result = subprocess.run(
            install_cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode == 0:
            try:
                import librosa  # noqa: F401

                print("[green]✅ librosa installed successfully[/green]")
                logger.info("librosa installed successfully")
                return True
            except ImportError:
                print(
                    "[yellow]⚠️  librosa installation completed but import failed. Please restart the application.[/yellow]"
                )
                logger.warning("librosa installation completed but import failed")
                return False
        error_output = result.stderr or result.stdout or ""
        is_llvm_error = (
            "llvmlite" in error_output.lower() or "llvm" in error_output.lower()
        )
        if is_macos and is_llvm_error:
            print(
                "[yellow]⚠️  librosa installation failed due to LLVM dependency issue.[/yellow]"
            )
            print("[dim]On macOS, install LLVM via Homebrew: brew install llvm[/dim]")
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
        print(
            "[yellow]⚠️  Could not install librosa automatically. Using size-only duplicate detection.[/yellow]"
        )
        print("[dim]Install manually with: pip install librosa>=0.10.0[/dim]")
        logger.warning(f"Error checking/installing librosa: {e}", exc_info=True)
        return False


def _find_streamlit_app() -> Path | None:
    """Find the Streamlit app.py file using multiple fallback methods."""
    try:
        from importlib import import_module

        module = import_module("transcriptx.web.app")
        module_file = getattr(module, "__file__", None)
        if module_file:
            candidate = Path(module_file)
            if candidate.exists():
                return candidate
    except Exception:
        pass

    # __file__ is .../src/transcriptx/cli/interactive_menu.py -> parent.parent = transcriptx, parent.parent.parent = src
    src_root = Path(__file__).resolve().parent.parent.parent
    streamlit_app = src_root / "transcriptx" / "web" / "app.py"
    if streamlit_app.exists():
        return streamlit_app

    cwd_app = Path.cwd() / "src" / "transcriptx" / "web" / "app.py"
    if cwd_app.exists():
        return cwd_app

    try:
        import transcriptx

        package_path = Path(transcriptx.__file__).parent
        package_app = package_path / "web" / "app.py"
        if package_app.exists():
            return package_app
    except (ImportError, AttributeError):
        pass

    current = Path.cwd()
    for _ in range(5):
        test_app = current / "src" / "transcriptx" / "web" / "app.py"
        if test_app.exists():
            return test_app
        if current == current.parent:
            break
        current = current.parent

    return None


def _running_in_docker() -> bool:
    """Return True if we appear to be running inside a Docker container."""
    return Path("/.dockerenv").exists()


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
            print(
                "[dim]Select an MP3, WAV, or other audio file to run preprocessing.[/dim]"
            )
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


def _show_browser_menu() -> None:
    """Launch the Streamlit web interface in the browser."""
    port = 8501
    host = "0.0.0.0" if _running_in_docker() else "127.0.0.1"
    url = f"http://{host}:{port}"
    user_url = "http://localhost:8501" if _running_in_docker() else url

    try:
        if not _check_and_install_streamlit(allow_install=True):
            print("[yellow]⚠️  Streamlit is required for the web interface.[/yellow]")
            print(
                "[dim]Please install it manually with: pip install streamlit>=1.29.0[/dim]"
            )
            return

        streamlit_app = _find_streamlit_app()
        if streamlit_app is None:
            print("[red]Streamlit app not found at: src/transcriptx/web/app.py[/red]")
            print(
                "[yellow]Please ensure you're running from the project root directory.[/yellow]"
            )
            return

        print(f"[green]Starting Streamlit web interface on {user_url}[/green]")
        if _running_in_docker():
            print("[cyan]In Docker: open the URL above in your host browser.[/cyan]")
        else:
            print("[cyan]Opening browser...[/cyan]")

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

        time.sleep(2)
        if not _running_in_docker():
            webbrowser.open(user_url)
        print("[green]✓ Browser UI has been started and opened in your browser[/green]")
        print(f"[dim]Access at: {user_url}[/dim]")
        print("[dim]Note: Keep this CLI session open to keep the server running.[/dim]")
        print(
            "[dim]Press Enter to stop the server and return to the main menu...[/dim]"
        )
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                process.kill()
            print("[dim]Browser UI stopped. Returning to Interface menu.[/dim]")

    except FileNotFoundError:
        log_error(
            "CLI",
            "Streamlit not found. Please install it with: pip install streamlit",
            exception=None,
        )
        print(
            "[red]Streamlit not found. Please install it with: pip install streamlit[/red]"
        )
    except Exception as e:
        log_error("CLI", f"Failed to start web viewer: {e}", exception=e)
        print(f"[red]Failed to start web viewer: {e}[/red]")
        print(
            "[yellow]You can also start it manually with: transcriptx web-viewer[/yellow]"
        )


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


def run_interactive_menu() -> None:
    """
    Run the main interactive menu loop.

    Called from main.py after config loading, startup checks, and banner.
    All menu choices and submenus are handled here.

    .. deprecated::
        Interactive terminal menus are deprecated. Use `transcriptx gui` for
        the primary interactive experience. CLI commands and flags remain
        fully supported.
    """
    print(
        "\n[yellow]⚠️  Interactive terminal menus are deprecated. "
        "Use `transcriptx gui` for the primary interactive experience. "
        "CLI commands and flags remain fully supported.[/yellow]\n"
    )

    while True:
        try:
            choice = questionary.select(
                "What would you like to do?",
                choices=[
                    "🔧 Preprocessing",
                    "🗣️  Manage Speakers",
                    "👥 Groups",
                    "✏️  Post-processing",
                    "📊 Analyze",
                    "🧪 Test Analysis",
                    "📁 Prep Audio",
                    "📊 Batch Analyze",
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

        elif choice == "📁 Prep Audio":
            from .file_selection_utils import (
                get_recordings_folder_start_path,
                select_folder_interactive,
            )
            from .prep_audio_workflow import run_prep_audio_workflow

            folder = select_folder_interactive(
                get_recordings_folder_start_path(get_config())
            )
            if folder is not None:
                run_prep_audio_workflow(folder)

        elif choice == "📊 Batch Analyze":
            from .batch_analyze_workflow import run_batch_analyze_workflow
            from .file_selection_utils import select_folder_interactive

            config = get_config()
            default_folder = Path(config.output.default_transcript_folder)
            folder = select_folder_interactive(default_folder)
            if folder is not None:
                run_batch_analyze_workflow(folder)

        elif choice == "🧭 Interface":
            _show_interface_menu()

        elif choice == "⚙️  Settings":
            from transcriptx.cli.config_editor import edit_config_interactive

            edit_config_interactive()

        elif choice == "🚪 Exit":
            print("\n[green]👋 Thanks for using TranscriptX![/green]")
            logger.info("User exited TranscriptX")
            exit_success()
