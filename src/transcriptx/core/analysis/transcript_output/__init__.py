"""
Transcript Output Generation Module for TranscriptX.

This module provides human-friendly transcript output generation capabilities.
"""

from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule


class TranscriptOutputAnalysis(AnalysisModule):
    """
    Transcript output generation module.

    This module generates human-friendly transcript outputs from analysis results.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the transcript output module."""
        super().__init__(config)
        self.module_name = "transcript_output"

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Perform transcript output generation (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility)

        Returns:
            Dictionary containing transcript output results
        """
        # This module primarily generates output, so analysis is minimal
        return {
            "segments": segments,
            "speaker_map": speaker_map or {},
            "total_segments": len(segments),
        }

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save results using OutputService (new interface).

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        # Generate transcript output using utility function
        from transcriptx.core.utils.transcript_output import (
            generate_human_friendly_transcript_from_file,
        )

        generate_human_friendly_transcript_from_file(output_service.transcript_path)


__all__ = ["TranscriptOutputAnalysis"]
