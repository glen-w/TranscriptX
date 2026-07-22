"""Download row renderer for transcript viewer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from transcriptx.web.components.action_links import render_download_link
from transcriptx.web.transcript_view_state import TranscriptArtifactsResult

_DOWNLOAD_ICON = ":material/download:"


def _read_bytes(path: Path) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def render_download_row(
    artifacts: TranscriptArtifactsResult,
    transcript_data: dict[str, Any],
    selected_session: str,
    *,
    run_root: Path | None = None,
) -> None:
    """Render TXT/CSV/SRT/JSON(/chapters) download links in the shared icon/text style."""
    items: list[tuple[str, bytes, str, str, str]] = []

    if artifacts.txt_file and artifacts.txt_file.exists():
        items.append(
            (
                "TXT",
                _read_bytes(artifacts.txt_file),
                artifacts.txt_file.name,
                "text/plain",
                "download_txt",
            )
        )
    if artifacts.csv_file and artifacts.csv_file.exists():
        items.append(
            (
                "CSV",
                _read_bytes(artifacts.csv_file),
                artifacts.csv_file.name,
                "text/csv",
                "download_csv",
            )
        )
    if artifacts.srt_file and artifacts.srt_file.exists():
        items.append(
            (
                "SRT",
                _read_bytes(artifacts.srt_file),
                artifacts.srt_file.name,
                "application/x-subrip",
                "download_srt",
            )
        )
    if artifacts.json_file and artifacts.json_file.exists():
        items.append(
            (
                "JSON",
                _read_bytes(artifacts.json_file),
                artifacts.json_file.name,
                "application/json",
                "download_json",
            )
        )
    else:
        transcript_json = json.dumps(transcript_data, indent=2, default=str)
        items.append(
            (
                "JSON",
                transcript_json.encode("utf-8"),
                f"{selected_session}_transcript.json",
                "application/json",
                "download_json",
            )
        )

    if run_root is not None:
        from transcriptx.core.analysis.topic_shift.visibility import (
            resolve_topic_shift_visibility,
            topic_shift_enrichment_path,
            topic_shift_spans_path,
        )

        if resolve_topic_shift_visibility(run_root) == "show":
            spans_path = topic_shift_spans_path(run_root)
            if spans_path.is_file():
                items.append(
                    (
                        "Chapters",
                        _read_bytes(spans_path),
                        f"{selected_session}_topic_shift_chapters.json",
                        "application/json",
                        "download_topic_shift_chapters",
                    )
                )
            enrich_path = topic_shift_enrichment_path(run_root)
            if enrich_path.is_file():
                items.append(
                    (
                        "Chapter titles",
                        _read_bytes(enrich_path),
                        f"{selected_session}_topic_shift_enrichment.json",
                        "application/json",
                        "download_topic_shift_enrichment",
                    )
                )

    cols = st.columns(len(items), gap="small")
    for col, (label, data, file_name, mime, key) in zip(cols, items, strict=True):
        with col:
            render_download_link(
                label,
                data=data,
                file_name=file_name,
                mime=mime,
                key=key,
                icon=_DOWNLOAD_ICON,
            )
