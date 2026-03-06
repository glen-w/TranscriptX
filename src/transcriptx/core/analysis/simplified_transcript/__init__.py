"""
Simplified Transcript Module for TranscriptX.

Produces a cleaned transcript (tics, hesitations, agreements, repetitions removed)
as part of analysis runs. Output is written to the run's transcripts subfolder.
"""

from pathlib import Path
from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.io import save_json
from .simplify import SimplifierConfig, TranscriptSimplifier


# Default tics/agreements; can be overridden via config or future tics module integration
DEFAULT_TICS = ["um", "uh", "like", "you know", "I mean"]
DEFAULT_AGREEMENTS = ["yeah", "right", "absolutely", "I agree", "sure"]


class SimplifiedTranscriptAnalysis(AnalysisModule):
    """
    Simplified transcript generation module.

    Removes tics, hesitations, agreement-only turns, and consecutive repetitions,
    then writes the simplified transcript JSON to the analysis run output.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the simplified transcript module."""
        super().__init__(config)
        self.module_name = "simplified_transcript"
        cfg = (config or {}).get("simplified_transcript", config or {})
        if isinstance(cfg, dict):
            self.tics = cfg.get("tics", DEFAULT_TICS)
            self.agreements = cfg.get("agreements", DEFAULT_AGREEMENTS)
        else:
            self.tics = DEFAULT_TICS
            self.agreements = DEFAULT_AGREEMENTS

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Build simplified transcript from segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments (must have 'speaker' and 'text').
            speaker_map: Unused; kept for interface compatibility.

        Returns:
            Dictionary with "simplified" (list of {speaker, text}),
            "total_original", "total_simplified".
        """
        transcript = [
            {"speaker": seg.get("speaker", ""), "text": seg.get("text", "")}
            for seg in segments
        ]
        simplifier = TranscriptSimplifier(self.tics, self.agreements)
        simplified = simplifier.simplify(transcript, verbose=False)
        return {
            "simplified": simplified,
            "total_original": len(segments),
            "total_simplified": len(simplified),
        }

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Write simplified transcript JSON and summary to the run's transcripts
        subfolder ({transcript_dir}/transcripts/) so they sit with other
        transcript outputs; artifacts are recorded.
        """
        transcripts_dir = Path(output_service.transcript_dir) / "transcripts"
        transcripts_dir.mkdir(parents=True, exist_ok=True)
        base = output_service.base_name

        simplified = results.get("simplified", [])
        simplified_path = transcripts_dir / f"{base}_simplified_transcript.json"
        save_json(simplified, str(simplified_path))
        output_service._record_artifact(simplified_path, "json")

        summary = {
            "total_original": results.get("total_original", 0),
            "total_simplified": results.get("total_simplified", 0),
            "removed_count": results.get("total_original", 0)
            - results.get("total_simplified", 0),
        }
        summary_path = transcripts_dir / f"{base}_simplified_transcript_summary.json"
        save_json(summary, str(summary_path))
        output_service._record_artifact(summary_path, "json", artifact_role="summary")


__all__ = ["SimplifiedTranscriptAnalysis", "SimplifierConfig", "TranscriptSimplifier"]
