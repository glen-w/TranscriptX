"""
Deprecated legacy Streamlit entry point (stub).

Canonical GUI module: ``transcriptx.web.app``.
Scheduled for removal after 1–2 release batches.
See ``docs/public_surfaces.md`` §2.4.
"""

from __future__ import annotations

import sys

_DEPRECATION_MESSAGE = """\
ERROR: src/transcriptx/web/streamlit_app.py is deprecated.

Use the canonical entry point transcriptx.web.app instead:
  transcriptx
  python -m transcriptx.web
  streamlit run src/transcriptx/web/app.py
"""


def _running_under_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except ImportError:
        return False
    return get_script_run_ctx() is not None


def main() -> None:
    """Print deprecation guidance and exit with a non-zero status."""
    sys.stderr.write(_DEPRECATION_MESSAGE)
    sys.exit(1)


if __name__ == "__main__":
    if _running_under_streamlit():
        # streamlit run catches sys.exit; show the message in the UI instead.
        import streamlit as st

        st.error(_DEPRECATION_MESSAGE.strip())
        st.stop()
    main()
