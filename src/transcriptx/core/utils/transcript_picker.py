"""Light transcript path/label listing for pickers (no Streamlit, no segment parse)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TranscriptPickerOption:
    """Path + display label for transcript pickers."""

    path: str
    label: str


def _under_managed_library(path: Path) -> bool:
    """True when path resolves under the configured transcripts library root."""
    from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR

    try:
        path.resolve().relative_to(Path(DIARISED_TRANSCRIPTS_DIR).resolve())
        return True
    except (ValueError, OSError):
        return False


def _is_picker_eligible(path: Path) -> bool:
    """Library paths need an import sidecar; non-library paths stay eligible.

    Cheap filesystem check only — no JSON parse / managed revalidation — so
    first paint stays fast. Raw WhisperX JSON dropped into the library root
    (no sidecar) is excluded until managed admit.
    """
    if not _under_managed_library(path):
        return True
    from transcriptx.io.import_metadata_sidecar import find_existing_import_sidecar

    return find_existing_import_sidecar(path) is not None


def list_transcript_picker_options() -> list[TranscriptPickerOption]:
    """Build picker rows from the slug index and on-disk discovery.

    Avoids managed revalidation and per-file segment loads. Analysis readiness /
    launch / studio start still validate the chosen path(s). Paths under the
    managed transcripts library without an import sidecar are omitted.
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
            if not _is_picker_eligible(path):
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
            if not _is_picker_eligible(path):
                continue
            resolved = str(path.resolve())
        except OSError:
            continue
        if resolved in rows:
            continue
        rows[resolved] = path.stem or resolved

    ordered = sorted(rows.items(), key=lambda item: (item[1].casefold(), item[0]))
    return [TranscriptPickerOption(path=path, label=label) for path, label in ordered]
