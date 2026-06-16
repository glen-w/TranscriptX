"""
Library controller. Discovery and inspection of transcripts. No prompts, no prints.
"""

from __future__ import annotations

from pathlib import Path

from transcriptx.app.models.metadata import TranscriptMetadata
from transcriptx.app.models.errors import PathConfigError

from transcriptx.core.utils.file_discovery import discover_managed_transcript_paths
from transcriptx.core.utils.speaker_extraction import named_speaker_count_for_path
from transcriptx.io.speaker_map_resolver import SpeakerMapResolver
from transcriptx.core.utils._path_core import get_transcript_dir


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
        return SpeakerMapResolver().has_named_speakers(str(path))
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


def _segments_duration_seconds(segments: list[dict]) -> float | None:
    """Compute transcript duration from segment start/end timestamps."""
    times: list[tuple[float, float]] = []
    for seg in segments:
        try:
            start = float(seg.get("start"))
            end = float(seg.get("end"))
        except (TypeError, ValueError):
            continue
        if end >= start:
            times.append((start, end))
    if not times:
        return None
    min_start = min(start for start, _ in times)
    max_end = max(end for _, end in times)
    duration = max_end - min_start
    return duration if duration >= 0 else None


class LibraryController:
    """Orchestrates transcript discovery and metadata. No prompts, no prints."""

    def list_transcripts(self, root: Path | None = None) -> list[TranscriptMetadata]:
        """List transcripts with metadata. Uses existing discovery logic."""
        try:
            paths = discover_managed_transcript_paths(root)
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
            from transcriptx.core.audio import get_audio_duration

            duration = get_audio_duration(str(path))
        except Exception:
            pass
        segment_count: int | None = None
        speaker_map_status = "none"
        unidentified_speaker_count = 0
        ignored_speaker_count = 0
        try:
            from transcriptx.io import load_segments

            from transcriptx.services.speaker_studio.segment_index import (
                transcript_summary_from_loaded_segments,
            )

            segments = load_segments(str(path))
            if duration is None:
                duration = _segments_duration_seconds(segments)
            speaker_count = len(
                set(seg.get("speaker") for seg in segments if seg.get("speaker"))
            )
            ts = transcript_summary_from_loaded_segments(path, segments)
            segment_count = ts.segment_count
            speaker_map_status = ts.speaker_map_status
            unidentified_speaker_count = ts.unidentified_speaker_count
            ignored_speaker_count = ts.ignored_speaker_count
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
            segment_count=segment_count,
            speaker_map_status=speaker_map_status,
            unidentified_speaker_count=unidentified_speaker_count,
            ignored_speaker_count=ignored_speaker_count,
        )
