"""
Diagnostics page - doctor, dependency status.
"""

from __future__ import annotations

import streamlit as st

from transcriptx.web.cache_helpers import (
    cached_doctor_report,
    cached_group_manifest_warnings,
)


def render_diagnostics_page() -> None:
    """Render the diagnostics page."""
    st.markdown(
        '<div class="main-header">🔧 Diagnostics</div>',
        unsafe_allow_html=True,
    )

    report = cached_doctor_report()

    group_warnings = cached_group_manifest_warnings()
    if group_warnings:
        st.subheader("Group manifests")
        st.warning(
            "One or more group manifest files could not be loaded (for example, a member "
            "transcript path no longer exists). Fix or remove the manifest under **data/groups** "
            "or restore the missing files."
        )
        for line in group_warnings:
            st.code(line, language=None)

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

    st.caption(
        "For machine-readable diagnostics, use the Python API (e.g. the same report source this "
        "page uses) or extend `DiagnosticsController` in your own tooling."
    )
