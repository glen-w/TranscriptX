"""
CLI startup checks and guards.

Run once before the interactive loop. Keeps main.py focused on wiring.
"""

import contextlib
import sys
import builtins

from transcriptx.core.utils.logger import get_logger
from transcriptx.utils.spinner import SpinnerManager

logger = get_logger()


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


def _check_audio_playback_dependencies() -> None:
    """
    Check audio playback dependencies on startup.
    Informs user about available features (basic playback vs. seeking support).
    """
    import shutil

    try:
        from transcriptx.cli.audio import check_ffplay_available

        ffplay_available, _ = check_ffplay_available()
        is_macos = sys.platform == "darwin"
        afplay_available = is_macos and shutil.which("afplay") is not None

        if ffplay_available:
            logger.info(
                "Audio playback: ffplay available (full features including seeking)"
            )
        elif afplay_available:
            logger.info(
                "Audio playback: afplay available (basic playback only, no seeking)"
            )
            from rich import print

            print(
                "[dim]ℹ️  Audio playback: Basic playback available. Install ffmpeg (ffplay) for skip forward/backward controls.[/dim]"
            )
        else:
            logger.warning("Audio playback: No playback tools available")
            from rich import print

            print(
                "[yellow]⚠️  Audio playback: No playback tools found. Install ffmpeg (ffplay) for audio playback features.[/yellow]"
            )

    except Exception as e:
        logger.warning(
            f"Error checking audio playback dependencies: {e}", exc_info=True
        )


def _ensure_playwright_ready() -> None:
    """
    Ensure Playwright package and browser are ready for use.
    This proactively installs Playwright if needed, avoiding warnings during NER analysis.
    """
    try:
        from transcriptx.core.utils.lazy_imports import ensure_playwright_ready

        if ensure_playwright_ready(silent=True):
            logger.info("Playwright: Ready for NER location map rendering")
        else:
            logger.debug(
                "Playwright: Not available (NER location maps will be HTML-only)"
            )
    except Exception as e:
        logger.debug(f"Playwright check skipped: {e}")


def _ensure_pdf_ready() -> None:
    """
    Ensure PDF dependencies (reportlab) are installed in the active venv.
    Lazy-loaded; installs on first use so summary all-charts PDF works when needed.
    """
    try:
        from transcriptx.core.utils.lazy_imports import ensure_pdf_ready

        if ensure_pdf_ready(silent=True):
            logger.debug("PDF deps: ready for summary charts")
        else:
            logger.debug(
                "PDF deps: not available (summary all-charts PDF will be skipped)"
            )
    except Exception as e:
        logger.debug(f"PDF deps check skipped: {e}")
