"""
RecordingsService — audio file discovery and metadata for the web layer.

Responsibilities:
- List audio files available for preprocessing
- Extract file-level metadata (duration, sample rate, channels, format, size)
- Persist uploaded files into a stable imports/ subdirectory

Storage note (v1):
    Uploaded files are written durably to <recordings_dir>/imports/.
    No cleanup or retention policy is applied in this release; that is
    future work.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import streamlit as st

from transcriptx.core.audio.types import AudioFileMeta
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}
_IMPORTS_SUBDIR = "imports"


class RecordingsService:
    """Audio file discovery and metadata helper for the GUI."""

    @staticmethod
    @st.cache_data(ttl=30)
    def list_recordings(directory: Path) -> List[Path]:
        """
        Return all audio files under *directory*, sorted by name.

        Results are cached for 30 seconds so the selectbox refreshes
        without a full Streamlit restart.
        """
        if not directory.exists():
            return []
        files = sorted(
            p
            for p in directory.rglob("*")
            if p.is_file() and p.suffix.lower() in _AUDIO_EXTENSIONS
        )
        return files

    @staticmethod
    def get_audio_metadata(path: Path) -> AudioFileMeta:
        """
        Extract basic metadata from an audio file using pydub.

        Returns a best-effort AudioFileMeta.  On failure, all numeric
        fields default to 0 so callers never need to handle None.
        """
        try:
            from pydub import AudioSegment  # type: ignore[import]

            audio = AudioSegment.from_file(str(path))
            duration_sec = len(audio) / 1000.0
            file_size_mb = path.stat().st_size / (1024 * 1024)

            return AudioFileMeta(
                duration_sec=round(duration_sec, 1),
                sample_rate=audio.frame_rate,
                channels=audio.channels,
                format=path.suffix.lstrip(".").upper(),
                file_size_mb=round(file_size_mb, 2),
            )
        except Exception as e:
            logger.warning(f"Could not read metadata for {path.name}: {e}")
            return AudioFileMeta(
                duration_sec=0.0,
                sample_rate=0,
                channels=0,
                format=path.suffix.lstrip(".").upper(),
                file_size_mb=(
                    round(path.stat().st_size / (1024 * 1024), 2)
                    if path.exists()
                    else 0.0
                ),
            )

    @staticmethod
    def save_uploaded_file(uploaded_file: object, recordings_dir: Path) -> Path:
        """
        Write a Streamlit UploadedFile to <recordings_dir>/imports/<filename>.

        The imports/ directory is created if it does not exist.
        Files are stored durably; cleanup is future work.

        Args:
            uploaded_file: st.UploadedFile instance
            recordings_dir: Root recordings directory

        Returns:
            Path to the saved file
        """
        imports_dir = recordings_dir / _IMPORTS_SUBDIR
        imports_dir.mkdir(parents=True, exist_ok=True)

        dest = imports_dir / uploaded_file.name  # type: ignore[union-attr]
        dest.write_bytes(uploaded_file.read())  # type: ignore[union-attr]
        logger.info(f"Saved uploaded file to {dest}")
        return dest

    @staticmethod
    def format_duration(duration_sec: float) -> str:
        """Format duration seconds as mm:ss or h:mm:ss."""
        total = int(duration_sec)
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
