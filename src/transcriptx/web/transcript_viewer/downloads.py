"""Download row renderer for transcript viewer."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from transcriptx.web.transcript_view_state import TranscriptArtifactsResult


def render_download_row(
    artifacts: TranscriptArtifactsResult,
    transcript_data: dict[str, Any],
    selected_session: str,
) -> None:
    """Render TXT/CSV/SRT/JSON download controls."""
    download_label_col, txt_col, csv_col, srt_col, json_col = st.columns(
        [2, 1, 1, 1, 1]
    )
    with download_label_col:
        st.markdown("📥 Download:")

    with txt_col:
        if artifacts.txt_file and artifacts.txt_file.exists():
            with open(artifacts.txt_file, "rb") as f:
                st.download_button(
                    label="TXT",
                    data=f.read(),
                    file_name=artifacts.txt_file.name,
                    mime="text/plain",
                    key="download_txt",
                    type="tertiary",
                )
        else:
            st.caption("TXT")

    with csv_col:
        if artifacts.csv_file and artifacts.csv_file.exists():
            with open(artifacts.csv_file, "rb") as f:
                st.download_button(
                    label="CSV",
                    data=f.read(),
                    file_name=artifacts.csv_file.name,
                    mime="text/csv",
                    key="download_csv",
                    type="tertiary",
                )
        else:
            st.caption("CSV")

    with srt_col:
        if artifacts.srt_file and artifacts.srt_file.exists():
            with open(artifacts.srt_file, "rb") as f:
                st.download_button(
                    label="SRT",
                    data=f.read(),
                    file_name=artifacts.srt_file.name,
                    mime="application/x-subrip",
                    key="download_srt",
                    type="tertiary",
                )
        else:
            st.caption("SRT")

    with json_col:
        if artifacts.json_file and artifacts.json_file.exists():
            with open(artifacts.json_file, "rb") as f:
                st.download_button(
                    label="JSON",
                    data=f.read(),
                    file_name=artifacts.json_file.name,
                    mime="application/json",
                    key="download_json",
                    type="tertiary",
                )
        else:
            transcript_json = json.dumps(transcript_data, indent=2, default=str)
            st.download_button(
                label="JSON",
                data=transcript_json,
                file_name=f"{selected_session}_transcript.json",
                mime="application/json",
                key="download_json",
                type="tertiary",
            )
