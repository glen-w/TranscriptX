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


def _find_streamlit_app() -> Path | None:
    """Locate the Streamlit app.py relative to this package."""
    this_dir = Path(__file__).resolve().parent
    app_file = this_dir / "app.py"
    if app_file.exists():
        return app_file
    return None


def main(host: str = "127.0.0.1", port: int = 8501) -> None:
    """
    Launch the Streamlit web interface.

    Host and port can be overridden via ``TRANSCRIPTX_HOST`` /
    ``TRANSCRIPTX_PORT`` environment variables, or the first two positional
    CLI arguments (``transcriptx [--host HOST] [--port PORT]``).
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

    print(f"Starting TranscriptX web interface on http://{args.host}:{args.port}")
    sys.exit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
