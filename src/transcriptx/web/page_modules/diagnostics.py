"""
Diagnostics page - doctor, dependency status, incomplete rename repair.
"""

from __future__ import annotations

import streamlit as st

from transcriptx.web.cache_helpers import (
    cached_doctor_report,
    cached_group_manifest_warnings,
)


def _render_rename_repair_section() -> None:
    st.subheader("Incomplete renames")
    try:
        from transcriptx.core.utils.rename import (
            discover_incomplete_renames,
            repair_managed_rename,
        )
    except Exception as e:
        st.caption(f"Rename repair unavailable: {e}")
        return

    try:
        incomplete = list(discover_incomplete_renames())
    except Exception as e:
        st.error(f"Could not scan rename journal: {e}")
        return

    if not incomplete:
        st.caption("No incomplete managed rename operations found.")
        return

    st.warning(
        f"Found {len(incomplete)} incomplete rename operation"
        f"{'s' if len(incomplete) != 1 else ''}. "
        "Use Repair to resume a crash-safe rename, or inspect the journal manually."
    )
    for record in incomplete:
        op_id = getattr(record, "operation_id", None) or "?"
        with st.container(border=True):
            st.markdown(f"**Operation** `{op_id}`")
            st.caption(f"Phase: {getattr(record, 'phase', '?')}")
            old_p = getattr(record, "old_transcript_path", "") or "?"
            new_p = getattr(record, "new_transcript_path", "") or "?"
            st.caption(f"{old_p} → {new_p}")
            if st.button(
                "Repair incomplete rename",
                key=f"repair_rename_{op_id}",
                type="primary",
            ):
                try:
                    outcome = repair_managed_rename(str(op_id))
                    ok = bool(getattr(outcome, "ok", False))
                    message = getattr(outcome, "message", None) or str(outcome)
                    if ok:
                        st.success(message)
                    else:
                        st.error(message)
                    st.rerun()
                except Exception as e:
                    st.error(f"Repair failed: {e}")


def render_diagnostics_page() -> None:
    """Render the diagnostics page."""
    st.markdown(
        '<div class="main-header">Diagnostics</div>',
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

    _render_rename_repair_section()

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
