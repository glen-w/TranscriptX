from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.corrections.workflow import run_corrections_on_segments
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


class CorrectionsAnalysis(AnalysisModule):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.module_name = "corrections"

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        raise NotImplementedError(
            "CorrectionsAnalysis uses run_from_context to access config and output."
        )

    def run_from_context(self, context: "PipelineContext") -> Dict[str, Any]:
        config = get_config()
        corrections_config = getattr(config.analysis, "corrections", None)
        if corrections_config is None or not corrections_config.enabled:
            logger.info("Corrections module disabled in config.")
            return {"status": "skipped"}

        logger.warning(
            "CorrectionsAnalysis is deprecated in analysis pipelines. "
            "Use the post-processing corrections workflow instead."
        )

        segments = context.get_segments()
        transcript_path = context.transcript_path

        results = run_corrections_on_segments(
            segments=segments,
            transcript_path=transcript_path,
            transcript_key=context.transcript_key,
            speaker_map=context.get_speaker_map(),
            config=config,
            interactive_review=corrections_config.interactive_review,
        )

        context.store_analysis_result(
            self.module_name,
            {
                "suggestions_count": results.get("suggestions_count", 0),
                "applied_count": results.get("applied_count", 0),
            },
        )

        return {
            "status": results.get("status", "success"),
            "suggestions_count": results.get("suggestions_count", 0),
            "applied_count": results.get("applied_count", 0),
            "artifacts": results.get("artifacts", []),
        }
