"""AppTest entry: show run health caption for TRANSCRIPTX_GUI_ACC_RUN_ROOT.

Uses the same ``build_run_status_summary`` presentation Overview curated blocks
use. Artifact health is forced healthy so the assertion targets execution labels
(partial / failed) rather than fixture manifest quirks.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from transcriptx.web.run_health_presentation import build_run_status_summary

_run_root = Path(os.environ["TRANSCRIPTX_GUI_ACC_RUN_ROOT"])
_summary = build_run_status_summary(
    _run_root,
    health={"status": "ok", "errors": [], "warnings": []},
)
st.markdown(
    '<div class="tx-page-shell-title">Overview</div>',
    unsafe_allow_html=True,
)
st.caption(f"Run status: {_summary.user_facing_label}")
