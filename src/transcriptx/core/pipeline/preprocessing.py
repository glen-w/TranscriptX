"""
Preprocessing service for TranscriptX pipeline.

This module handles transcript validation,
providing reusable logic for the analysis pipeline.
"""

import json
from typing import Dict, Any, Tuple
from pathlib import Path

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.validation import validate_transcript_file

logger = get_logger()


class PreprocessingService:
    """
    Service for handling transcript preprocessing tasks.

    This class provides centralized logic for:
    - Transcript file validation
    - Output directory preparation
    """

    def __init__(self):
        """Initialize the preprocessing service."""
        self.logger = get_logger()

    def validate_transcript(self, transcript_path: str) -> None:
        """
        Validate a transcript file (exists and is valid).
        Does not validate write permission on the transcript's directory;
        analysis outputs are written to OUTPUTS_DIR, not the transcript dir.

        Args:
            transcript_path: Path to the transcript file

        Raises:
            FileNotFoundError: If transcript file doesn't exist
            ValueError: If transcript file is invalid
        """
        self.logger.debug(f"Validating transcript: {transcript_path}")
        validate_transcript_file(transcript_path)
        self.logger.debug(f"Transcript validation successful: {transcript_path}")

    def prepare_transcript_data(
        self, transcript_path: str
    ) -> Tuple[Dict[str, Any], str]:
        """
        Prepare transcript data for analysis.

        Args:
            transcript_path: Path to the transcript file

        Returns:
            Tuple of (transcript_data, base_name)
        """
        try:
            with open(transcript_path, encoding="utf-8") as f:
                transcript_data = json.load(f)

            base_name = Path(transcript_path).stem
            return transcript_data, base_name

        except Exception as e:
            self.logger.error(f"Failed to load transcript data: {e}")
            raise


# Global preprocessing service instance
_preprocessing_service = PreprocessingService()


def validate_transcript(transcript_path: str) -> None:
    """Validate a transcript file."""
    _preprocessing_service.validate_transcript(transcript_path)


def prepare_transcript_data(transcript_path: str) -> Tuple[Dict[str, Any], str]:
    """Prepare transcript data for analysis."""
    return _preprocessing_service.prepare_transcript_data(transcript_path)
