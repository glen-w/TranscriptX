"""Light transcript path/label listing for pickers (no Streamlit, no segment parse)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TranscriptPickerOption:
    """Path + display label for transcript pickers."""

    path: str
    label: str


def list_transcript_picker_options() -> list[TranscriptPickerOption]:
    """Build picker rows from the slug index and on-disk discovery.

    Avoids managed revalidation and per-file segment loads. Analysis readiness /
    launch / studio start still validate the chosen path(s).
    """
    from transcriptx.core.utils.file_discovery import discover_all_transcript_paths
    from transcriptx.core.utils.slug_manager import list_all_transcripts

    rows: dict[str, str] = {}

    for entry in list_all_transcripts():
        source_path = entry.get("source_path")
        if not source_path:
            continue
        try:
            path = Path(str(source_path)).expanduser()
            if not path.exists():
                continue
            resolved = str(path.resolve())
        except OSError:
            continue
        label = str(entry.get("source_basename") or path.stem or resolved)
        rows[resolved] = label

    for path in discover_all_transcript_paths(None):
        try:
            if not path.exists():
                continue
            resolved = str(path.resolve())
        except OSError:
            continue
        if resolved in rows:
            continue
        rows[resolved] = path.stem or resolved

    ordered = sorted(rows.items(), key=lambda item: (item[1].casefold(), item[0]))
    return [TranscriptPickerOption(path=path, label=label) for path, label in ordered]
