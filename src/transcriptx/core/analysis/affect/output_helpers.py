"""Shared artifact-write helpers for sentiment / emotion (JSON-then-CSV order).

Entity sentiment uses CSV-then-JSON and must not call :func:`save_rows_json_csv`.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union

from transcriptx.core.output.output_service import OutputService
from transcriptx.core.utils._path_core import get_enriched_transcript_path
from transcriptx.io.file_io import save_transcript


def write_enriched_transcript(
    output_service: OutputService,
    segments: List[Dict[str, Any]],
    module_tag: str,
) -> str:
    """Write enriched transcript via path helpers + save_transcript; return path str."""
    enriched_path = get_enriched_transcript_path(
        output_service.transcript_path, module_tag
    )
    os.makedirs(os.path.dirname(enriched_path), exist_ok=True)
    save_transcript(segments, enriched_path)
    return enriched_path


def save_rows_json_csv(
    output_service: OutputService,
    data: Union[Dict[str, Any], List[Any], str],
    filename: str,
    *,
    subdirectory: Optional[str] = None,
    speaker: Optional[str] = None,
) -> tuple[str, str]:
    """Save the same payload as JSON then CSV via OutputService.save_data.

    Forwards subdirectory/speaker and preserves save_data overwrite/skip semantics.
    """
    json_path = output_service.save_data(
        data,
        filename,
        format_type="json",
        subdirectory=subdirectory,
        speaker=speaker,
    )
    csv_path = output_service.save_data(
        data,
        filename,
        format_type="csv",
        subdirectory=subdirectory,
        speaker=speaker,
    )
    return json_path, csv_path
