"""
Web entry point for TranscriptX.

Starts the Streamlit web interface. Invoked via the installed
``transcriptx`` console script, or directly with:

    python -m transcriptx.web
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Load .env before spawning Streamlit so subprocess inherits TRANSCRIPTX_* vars
from transcriptx._bootstrap import bootstrap

bootstrap()

# Pin BLAS/OpenMP/Numba before Streamlit imports analysis extras (BERTopic/UMAP).
# Pool size is process-sticky; late caps cannot undo macOS segfaults.
from transcriptx.core.utils.native_threads import (  # noqa: E402
    ensure_native_thread_env_defaults,
)

ensure_native_thread_env_defaults()


def _find_streamlit_app() -> Path | None:
    """Locate the Streamlit app.py relative to this package."""
    this_dir = Path(__file__).resolve().parent
    app_file = this_dir / "app.py"
    if app_file.exists():
        return app_file
    return None


_TRUTHY = {"1", "true", "on", "yes"}


def file_watcher_args(environ: "os._Environ[str] | dict[str, str]") -> list[str]:
    """Streamlit source-watcher flags for the launch command.

    Default launches are a product, not a dev loop: Streamlit's local sources
    watcher walks every imported module (transformers, torch, …) after each
    run and logs hundreds of ``Examining the path … raised`` tracebacks. Set
    ``TRANSCRIPTX_DEV=1`` to keep hot-reload, or ``TRANSCRIPTX_FILE_WATCHER``
    to pass an explicit Streamlit ``fileWatcherType`` (auto|watchdog|poll|none).
    """
    explicit = (environ.get("TRANSCRIPTX_FILE_WATCHER") or "").strip().lower()
    if explicit:
        return ["--server.fileWatcherType", explicit]
    if (environ.get("TRANSCRIPTX_DEV") or "").strip().lower() in _TRUTHY:
        return []
    return ["--server.fileWatcherType", "none"]


BRAND_PRIMARY_COLOR = "#1f77b4"


def theme_args(environ: "os._Environ[str] | dict[str, str]") -> list[str]:
    """Brand primary colour unless the operator set a Streamlit theme env var.

    Without this, Streamlit's default ``#FF4B4B`` paints active nav / primary
    buttons red (reads as an error state against the blue/green wordmark).
    """
    if environ.get("STREAMLIT_THEME_PRIMARY_COLOR"):
        return []
    return ["--theme.primaryColor", BRAND_PRIMARY_COLOR]


def main(host: str = "127.0.0.1", port: int = 8501) -> None:
    """
    Launch the Streamlit web interface.

    Host and port can be overridden via ``TRANSCRIPTX_HOST`` /
    ``TRANSCRIPTX_PORT`` environment variables, or the first two positional
    arguments (``transcriptx [--host HOST] [--port PORT]``).
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="transcriptx",
        description="TranscriptX — launch the web interface",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("TRANSCRIPTX_HOST", host),
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("TRANSCRIPTX_PORT", port)),
        help="Port to listen on (default: 8501)",
    )
    args = parser.parse_args()

    streamlit_app = _find_streamlit_app()
    if streamlit_app is None:
        print(
            "ERROR: Streamlit app not found. "
            "Ensure the package is installed correctly.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        result = subprocess.run(
            [sys.executable, "-c", "import streamlit"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            print(
                "ERROR: Streamlit is not installed. "
                "Install it with: pip install streamlit>=1.29.0",
                file=sys.stderr,
            )
            sys.exit(1)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(streamlit_app),
        "--server.port",
        str(args.port),
        "--server.address",
        args.host,
        "--server.headless",
        "true",
    ]
    cmd.extend(file_watcher_args(os.environ))
    cmd.extend(theme_args(os.environ))

    print(f"Starting TranscriptX web interface on http://{args.host}:{args.port}")
    sys.exit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
