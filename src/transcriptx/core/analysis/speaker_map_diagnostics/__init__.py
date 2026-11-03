"""Speaker-map / diarization consistency diagnostics (B19)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.speaker_map_diagnostics.analyze import (
    compute_speaker_map_diagnostics,
)
from transcriptx.io.speaker_map_resolver import SpeakerMapResolver


class SpeakerMapDiagnosticsAnalysis(AnalysisModule):
    """Per-run speaker-map honesty: unnamed vs named, map mismatches, tiers."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.module_name = "speaker_map_diagnostics"
        self._transcript_path: Optional[str] = None

    def analyze(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        mapping: dict[str, Any] = {}
        ignored: list[str] = []
        db_ids: dict[str, Any] = {}
        has_sidecar = False
        if self._transcript_path:
            state = SpeakerMapResolver().load_mapping(self._transcript_path)
            mapping = dict(state.speaker_map)
            ignored = list(state.ignored_speakers)
            db_ids = dict(getattr(state, "speaker_id_to_db_id", {}) or {})
            has_sidecar = bool(state.has_sidecar)
        treat_as_single = False
        allow_unnamed = False
        try:
            from transcriptx.core.utils.config import get_config

            analysis = get_config().analysis
            treat_as_single = bool(getattr(analysis, "treat_as_single_speaker", False))
            allow_unnamed = bool(getattr(analysis, "allow_unnamed_speakers", False))
        except Exception:
            pass
        return compute_speaker_map_diagnostics(
            segments,
            speaker_map=mapping,
            ignored_speakers=ignored,
            speaker_id_to_db_id=db_ids,
            treat_as_single_speaker=treat_as_single,
            allow_unnamed_speakers=allow_unnamed,
            has_sidecar=has_sidecar,
        )

    def run_from_context(self, context: Any) -> Dict[str, Any]:
        self._transcript_path = getattr(context, "transcript_path", None)
        try:
            return super().run_from_context(context)
        finally:
            self._transcript_path = None

    def _save_results(
        self,
        results: Dict[str, Any],
        output_service: "OutputService",
    ) -> None:
        output_service.save_data(results, "speaker_map_diagnostics", format_type="json")
