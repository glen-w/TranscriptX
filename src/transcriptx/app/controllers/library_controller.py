"""
Library controller. Discovery and inspection of transcripts. No prompts, no prints.
"""

from __future__ import annotations

from pathlib import Path

from transcriptx.app.models.metadata import TranscriptMetadata
from transcriptx.app.models.errors import PathConfigError

from transcriptx.app.compat import (
    discover_all_transcript_paths,
    named_speaker_count_for_path,
)
from transcriptx.io import load_segments
from transcriptx.io.transcript_loader import extract_speaker_map_from_transcript
from transcriptx.core.utils.speaker_extraction import count_named_speakers
from transcriptx.core.utils.path_utils import get_transcript_dir


def _has_analysis_outputs(path: Path) -> bool:
    """Check if transcript has analysis outputs."""
    try:
        out_dir = get_transcript_dir(str(path))
        return Path(out_dir).exists() and any(Path(out_dir).iterdir())
    except Exception:
        return False


def _has_speaker_map(path: Path) -> bool:
    """Check if transcript has speaker map (named speakers)."""
    try:
        segments = load_segments(str(path))
        speaker_map = extract_speaker_map_from_transcript(str(path))
        resolved = [dict(seg) for seg in segments]
        for seg in resolved:
            speaker = seg.get("speaker")
            if speaker is not None and speaker in speaker_map:
                seg["speaker"] = speaker_map[speaker]
        return count_named_speakers(resolved) > 0
    except Exception:
        return False


def _linked_run_dirs(path: Path) -> list[Path]:
    """Get run directories linked to this transcript."""
    try:
        out_dir = get_transcript_dir(str(path))
        base = Path(out_dir)
        if not base.exists():
            return []
        return [d for d in base.iterdir() if d.is_dir() and not d.name.startswith(".")]
    except Exception:
        return []


class LibraryController:
    """Orchestrates transcript discovery and metadata. No prompts, no prints."""

    def list_transcripts(self, root: Path | None = None) -> list[TranscriptMetadata]:
        """List transcripts with metadata. Uses existing discovery logic."""
        try:
            paths = discover_all_transcript_paths(root)
            result = []
            for p in paths:
                meta = self.get_transcript_metadata(p)
                result.append(meta)
            return result
        except Exception as e:
            raise PathConfigError(str(e)) from e

    def get_transcript_metadata(self, path: Path) -> TranscriptMetadata:
        """Get clean metadata for a transcript. Not display-oriented."""
        path = Path(path)
        base_name = path.stem if path.suffix else path.name
        duration: float | None = None
        speaker_count: int | None = None
        named_count: int | None = None
        try:
            from transcriptx.cli.audio import get_audio_duration

            duration = get_audio_duration(str(path))
        except Exception:
            pass
        try:
            from transcriptx.io import load_segments

            segments = load_segments(str(path))
            speaker_count = len(
                set(seg.get("speaker") for seg in segments if seg.get("speaker"))
            )
        except Exception:
            pass
        try:
            named_count = named_speaker_count_for_path(path)
        except Exception:
            pass
        has_outputs = _has_analysis_outputs(path)
        has_map = _has_speaker_map(path)
        linked = _linked_run_dirs(path)
        return TranscriptMetadata(
            path=path,
            base_name=base_name,
            duration_seconds=duration,
            speaker_count=speaker_count,
            named_speaker_count=named_count,
            has_analysis_outputs=has_outputs,
            has_speaker_map=has_map,
            linked_run_dirs=linked,
        )
