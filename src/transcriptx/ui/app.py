"""Local UI entrypoint (Gradio UI removed). Stub for backwards compatibility."""

from __future__ import annotations

import sys


def build_app():
    """Raise; Gradio UI has been removed."""
    raise RuntimeError(
        "The Gradio-based local UI has been removed. "
        "Use the Streamlit web viewer (transcriptx-web) or the CLI instead."
    )


def main(host: str = "127.0.0.1", port: int = 7860, open_browser: bool = True) -> None:
    """Exit with message; Gradio UI has been removed."""
    print(
        "The Gradio-based local UI has been removed. "
        "Use the Streamlit web viewer (transcriptx-web) or the CLI instead.",
        file=sys.stderr,
    )
    sys.exit(1)
