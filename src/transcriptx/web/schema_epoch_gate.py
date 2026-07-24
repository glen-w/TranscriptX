"""Streamlit gate for schema-epoch incompatible managed data roots.

Blocks principal work; offers remediation choices without automatic deletion.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.core.utils.paths import PATHS
from transcriptx.core.utils.schema_epoch import (
    CURRENT_SCHEMA_EPOCH,
    DataRootStatus,
    ensure_epoch_marker,
)
from transcriptx.core.utils.schema_epoch_remediation import (
    create_fresh_data_directory,
    export_transcript_inventory,
    inventory_compatible_transcripts,
    remediation_copy_for,
    reset_incompatible_derived_state,
    write_reset_report,
)


def render_schema_epoch_gate() -> bool:
    """Ensure epoch marker or block the app with remediation UX.

    Returns True when the caller should stop rendering principal work.
    """
    assessment = ensure_epoch_marker(PATHS.data_dir, initialize_empty=True)
    if assessment.status == DataRootStatus.COMPATIBLE:
        return False
    if assessment.status == DataRootStatus.EMPTY:
        # ensure_epoch_marker should have initialized; re-check
        assessment = ensure_epoch_marker(PATHS.data_dir, initialize_empty=True)
        if assessment.status == DataRootStatus.COMPATIBLE:
            return False

    st.title("Data directory needs an update")
    st.error(remediation_copy_for(assessment))
    st.markdown(
        f"**Incompatible root:** `{assessment.data_root}`  \n"
        f"**Required schema epoch:** `{CURRENT_SCHEMA_EPOCH}`  \n"
        f"**Status:** `{assessment.status.value}`"
    )
    st.info(
        "TranscriptX will not delete your data automatically. "
        "Source recordings are never touched. Compatible transcripts are "
        "preserved by default. Prefer creating a fresh data directory, then "
        "re-point `TRANSCRIPTX_DATA_DIR` (or Docker volume) at it."
    )
    st.markdown(
        "Backup guidance: copy your current data directory (or at least "
        "`transcripts/` and `recordings/`) before any reset. See "
        "`docs/dev/schema_epoch_inventory.md` for the epoch policy."
    )

    with st.expander("Optional: inventory managed transcripts", expanded=False):
        inventory = inventory_compatible_transcripts(assessment.data_root)
        st.write(f"Found **{inventory.count}** transcript JSON file(s).")
        if inventory.items:
            preview = [
                {"relative_path": i.relative_path, "size_bytes": i.size_bytes}
                for i in inventory.items[:50]
            ]
            st.dataframe(preview, use_container_width=True)
        export_path = st.text_input(
            "Export inventory JSON to",
            value=str(Path.home() / "transcriptx_epoch_transcript_inventory.json"),
            key="schema_epoch_inventory_export_path",
        )
        if st.button("Export transcript inventory", key="schema_epoch_export_inv"):
            try:
                path = export_transcript_inventory(inventory, Path(export_path))
                st.success(f"Wrote inventory to `{path}`")
            except OSError as exc:
                st.error(f"Could not write inventory: {exc}")

    st.subheader("Recommended: create a fresh data directory")
    fresh_path = st.text_input(
        "New empty data directory path",
        value=str(Path(assessment.data_root).parent / "transcriptx_data_epoch1"),
        key="schema_epoch_fresh_path",
    )
    if st.button("Create fresh epoch-1 data directory", type="primary"):
        try:
            created = create_fresh_data_directory(Path(fresh_path))
            st.success(
                f"Created `{created}` with schema epoch {CURRENT_SCHEMA_EPOCH}. "
                f"Set `TRANSCRIPTX_DATA_DIR={created}` (or your Docker mount) "
                f"and restart TranscriptX."
            )
        except (OSError, FileExistsError) as exc:
            st.error(str(exc))

    st.subheader("Advanced: reset incompatible derived state only")
    st.warning(
        "This removes derived app state under the current data root "
        "(outputs, caches, state, groups, corrections, speaker_profiles, "
        "backups) and writes an epoch marker. It does **not** delete "
        "`recordings/` or `transcripts/`."
    )
    confirm = st.text_input(
        "Type RESET DERIVED to confirm",
        key="schema_epoch_reset_confirm",
    )
    report_path = st.text_input(
        "Reset report path",
        value=str(Path.home() / "transcriptx_epoch_reset_report.json"),
        key="schema_epoch_reset_report_path",
    )
    if st.button("Reset derived state", key="schema_epoch_reset_derived"):
        if confirm.strip() != "RESET DERIVED":
            st.error("Confirmation text must be exactly: RESET DERIVED")
        else:
            report = reset_incompatible_derived_state(
                Path(assessment.data_root),
                write_epoch_marker=True,
                dry_run=False,
            )
            try:
                written = write_reset_report(report, Path(report_path))
                st.write(f"Reset report written to `{written}`")
            except OSError as exc:
                st.warning(f"Reset finished but report write failed: {exc}")
            if report.errors:
                st.error("Reset completed with errors:")
                for err in report.errors:
                    st.write(f"- {err}")
            else:
                st.success(
                    f"Removed {len(report.removed_paths)} derived path(s). "
                    f"Epoch marker written: {report.epoch_written}. "
                    "Restart or refresh to continue."
                )
                st.rerun()

    return True


__all__ = ["render_schema_epoch_gate"]
