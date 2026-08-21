"""
Diagnostics page - doctor, dependency status, incomplete rename repair.
"""

from __future__ import annotations

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.web.cache_helpers import (
    cached_doctor_report,
    cached_group_manifest_warnings,
)


def _render_speaker_profile_ops() -> None:
    st.subheader("Speaker profile operations")
    try:
        from transcriptx.core.speaker_profiles.integrity import run_integrity_scan
        from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
        from transcriptx.core.speaker_profiles.service import SpeakerProfileService
        from transcriptx.core.speaker_profiles.store_io import ensure_layout
        from transcriptx.web.speaker_profile_signals import (
            consume_cache_invalidation_signal,
        )
    except Exception as e:
        st.caption(f"Speaker profile diagnostics unavailable: {e}")
        return

    root = speaker_profiles_dir()
    try:
        root.mkdir(parents=True, exist_ok=True)
        ensure_layout(root)
        report = run_integrity_scan(root)
    except Exception as e:
        st.error(f"Could not scan speaker profile integrity: {e}")
        return

    if report.ok and not report.blocking_details and not report.corrupt_operations:
        st.caption("No blocking speaker-profile operations or corrupt op files.")
        return

    if not report.ok:
        st.warning(
            "Speaker profile integrity is not ok. "
            f"Blocking ops={len(report.blocking_operations)}, "
            f"corrupt profiles/links/events/ops="
            f"{len(report.corrupt_profiles)}/"
            f"{len(report.corrupt_links)}/"
            f"{len(report.corrupt_events)}/"
            f"{len(report.corrupt_operations)}."
        )

    if report.corrupt_operations:
        st.markdown("**Corrupt operation files**")
        for path in report.corrupt_operations:
            st.code(path, language=None)

    if not report.blocking_details:
        return

    st.markdown("**Blocking operations**")
    svc = SpeakerProfileService()
    for detail in report.blocking_details:
        with st.container(border=True):
            st.markdown(f"**Operation** `{detail.operation_id}`")
            st.caption(
                f"recovery_class=`{detail.recovery_class}` · phase=`{detail.phase}`"
            )
            if detail.affected_relpaths:
                st.code("\n".join(detail.affected_relpaths), language=None)
            if detail.profile_ids:
                st.caption("Profiles: " + ", ".join(detail.profile_ids))
            if detail.link_file_keys:
                st.caption("Link keys: " + ", ".join(detail.link_file_keys))
            if st.button(
                "Attempt safe recovery",
            icon=ic.REPLAY,
                key=f"diag_recover_{detail.operation_id}",
                type="primary",
            ):
                try:
                    result = svc.recover_operation(detail.operation_id)
                    consume_cache_invalidation_signal(result.cache_signal)
                    rc = result.report.recovery_class
                    if rc == "complete":
                        st.success(f"Recovery complete for `{detail.operation_id}`.")
                    elif rc == "proven_aborted":
                        st.info(f"Operation `{detail.operation_id}` proven aborted.")
                    elif rc == "needs_repair" or result.report.blocking:
                        st.warning(
                            f"Operation `{detail.operation_id}` still needs_repair "
                            f"(class=`{rc}`)."
                        )
                    else:
                        st.warning(
                            f"Recovery finished with class `{rc}` for "
                            f"`{detail.operation_id}`."
                        )
                    st.rerun()
                except Exception as e:
                    st.error(f"Recovery failed: {e}")


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
            icon=ic.RENAME,
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
        count = len(group_warnings)
        label = (
            f"{count} unloadable group manifest"
            if count == 1
            else f"{count} unloadable group manifests"
        )
        with st.expander(label, expanded=False):
            for line in group_warnings:
                st.code(line, language=None)

    _render_rename_repair_section()
    _render_speaker_profile_ops()

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
