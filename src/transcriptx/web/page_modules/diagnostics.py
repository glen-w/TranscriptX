"""
Diagnostics page - doctor, dependency status.
"""

from __future__ import annotations

import streamlit as st

from transcriptx.web.cache_helpers import cached_doctor_report


def render_diagnostics_page() -> None:
    """Render the diagnostics page."""
    st.markdown(
        '<div class="main-header">🔧 Diagnostics</div>',
        unsafe_allow_html=True,
    )

    report = cached_doctor_report()

    st.subheader("Environment")
    st.write(
        f"Config snapshot available: **{'yes' if report['config_snapshot_available'] else 'no'}**"
    )
    st.write(f"Dependencies tracked: **{len(report['dependency_versions'])}**")

    st.subheader("Dependency versions")
    deps = report.get("dependency_versions", {})
    if deps:
        for pkg, ver in sorted(deps.items()):
            st.text(f"  {pkg}: {ver}")
    else:
        st.info("No dependency versions available.")

    st.caption("For full diagnostics, run: transcriptx doctor --json")
