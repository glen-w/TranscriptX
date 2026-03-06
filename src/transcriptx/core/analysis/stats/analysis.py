"""Stats analysis module."""

from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.utils.text_utils import is_eligible_named_speaker

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.analysis.tics import extract_tics_and_top_words

logger = get_logger()


from .data_loader import load_module_data
from .summary import create_comprehensive_summary
from .stats_report import (
    build_stats_payload,
    render_stats_markdown,
    render_stats_txt,
)
from .speaker_stats import compute_speaker_stats


class StatsAnalysis(AnalysisModule):
    """
    Statistical analysis and report generation module.

    This module aggregates data from all analysis modules and generates
    comprehensive reports in multiple formats (TXT, HTML).
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the stats analysis module."""
        super().__init__(config)
        self.module_name = "stats"
        self.supports_aggregation = True

    def aggregate(
        self,
        per_transcript_results: List["PerTranscriptResult"],
        canonical_speaker_map: "CanonicalSpeakerMap",
        transcript_set: "TranscriptSet",
    ) -> Dict[str, Any]:
        from transcriptx.core.analysis.stats.aggregation import aggregate_stats_group

        return aggregate_stats_group(
            per_transcript_results,
            canonical_speaker_map,
            transcript_set,
        )

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str] = None,
        ignored_ids: set[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Perform statistical analysis on transcript segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility, not used)

        Returns:
            Dictionary containing statistical analysis results
        """
        import warnings

        if speaker_map is not None:
            warnings.warn(
                "speaker_map parameter is deprecated. Speaker identification now uses "
                "speaker_db_id from segments directly.",
                DeprecationWarning,
                stacklevel=2,
            )
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        # Group text by speaker
        grouped = {}
        for seg in segments:
            speaker_info = extract_speaker_info(seg)
            if speaker_info is None:
                continue
            name = get_speaker_display_name(speaker_info.grouping_key, [seg], segments)
            if not name or not is_eligible_named_speaker(
                name, str(speaker_info.grouping_key), ignored_ids or set()
            ):
                continue
            grouped.setdefault(name, []).append(seg.get("text", ""))

        # Load tics
        tic_list = extract_tics_and_top_words(grouped)
        if isinstance(tic_list, tuple):
            tic_list = list(tic_list)

        # Compute speaker statistics
        speaker_stats, sentiment_summary = compute_speaker_stats(
            grouped, segments, speaker_map, tic_list, ignored_ids=ignored_ids
        )

        return {
            "speaker_stats": speaker_stats,
            "sentiment_summary": sentiment_summary,
            "grouped_texts": grouped,
            "tic_list": tic_list,
        }

    def run_from_context(self, context: "PipelineContext") -> Dict[str, Any]:
        """
        Run stats analysis using PipelineContext (can access cached results from other modules).

        Args:
            context: PipelineContext containing transcript data and cached results

        Returns:
            Dictionary containing analysis results and metadata
        """
        try:
            from transcriptx.core.utils.logger import (
                log_analysis_start,
                log_analysis_complete,
                log_analysis_error,
            )

            log_analysis_start(self.module_name, context.transcript_path)

            # Extract data from context
            segments = context.get_segments()
            speaker_map = context.get_speaker_map()
            base_name = context.get_base_name()
            transcript_dir = context.get_transcript_dir()

            # Perform analysis
            ignored_ids = context.get_runtime_flags().get("ignored_speaker_ids")
            results = self.analyze(
                segments,
                speaker_map,
                ignored_ids=ignored_ids if isinstance(ignored_ids, set) else None,
            )

            # Try to load module data from context first (cached results)
            module_data = self._load_module_data_from_context(context)

            # Fall back to loading from files if context doesn't have all data
            if not module_data or not any(module_data.values()):
                module_data = load_module_data(transcript_dir, base_name)

            # Create comprehensive summary
            summary_text = create_comprehensive_summary(
                transcript_dir,
                base_name,
                results["speaker_stats"],
                results["sentiment_summary"],
                module_data,
                ignored_ids=(ignored_ids if isinstance(ignored_ids, set) else set()),
                speaker_key_aliases=context.get_runtime_flags().get(
                    "speaker_key_aliases", {}
                ),
            )

            # Create output service and save results
            from transcriptx.core.output.output_service import create_output_service

            output_service = create_output_service(
                context.transcript_path,
                self.module_name,
                output_dir=context.get_transcript_dir(),
                run_id=context.get_run_id(),
                runtime_flags=context.get_runtime_flags(),
            )

            # Save summary text
            output_service.save_data(
                summary_text, "comprehensive_summary", format_type="txt"
            )

            # Build stats payload (deterministic and debuggable)
            config_hash = _load_config_hash(transcript_dir)
            generator_overrides = {"git_sha": _load_git_sha()}
            stats_payload = build_stats_payload(
                context,
                segments,
                results,
                module_data,
                config_hash=config_hash,
                generator_overrides=generator_overrides,
            )

            import json
            from transcriptx.core.utils.artifact_writer import write_text
            from pathlib import Path

            stats_json_path = Path(transcript_dir) / f"{base_name}_stats.json"
            stats_md_path = Path(transcript_dir) / f"{base_name}_stats.md"
            stats_txt_path = Path(transcript_dir) / f"{base_name}_stats.txt"

            stats_json_text = json.dumps(
                stats_payload,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            write_text(stats_json_path, stats_json_text)
            write_text(stats_md_path, render_stats_markdown(stats_payload))
            write_text(stats_txt_path, render_stats_txt(stats_payload))

            # Explicitly register run-root artifacts for manifest metadata
            output_service._record_artifact_metadata(
                stats_json_path,
                {"scope": "global", "format": "json", "title": "Overall stats (JSON)"},
            )
            output_service._record_artifact_metadata(
                stats_md_path,
                {"scope": "global", "format": "md", "title": "Overall stats (MD)"},
            )
            output_service._record_artifact_metadata(
                stats_txt_path,
                {"scope": "global", "format": "txt", "title": "Overall stats (TXT)"},
            )

            # Store result in context
            context.store_analysis_result(self.module_name, results)

            log_analysis_complete(self.module_name, context.transcript_path)

            return {
                "module": self.module_name,
                "transcript_path": context.transcript_path,
                "status": "success",
                "results": results,
                "output_directory": str(
                    output_service.get_output_structure().module_dir
                ),
            }

        except Exception as e:
            from transcriptx.core.utils.logger import log_analysis_error

            log_analysis_error(self.module_name, context.transcript_path, str(e))
            return {
                "module": self.module_name,
                "transcript_path": context.transcript_path,
                "status": "error",
                "error": str(e),
                "results": {},
            }

    def _load_module_data_from_context(
        self, context: "PipelineContext"
    ) -> Dict[str, Any]:
        """Try to load module data from PipelineContext cached results."""
        module_data = {}

        # Try to get cached results from context
        module_names = [
            "acts",
            "interactions",
            "emotion",
            "sentiment",
            "ner",
            "wordclouds",
            "entity_sentiment",
            "conversation_loops",
            "contagion",
        ]

        for module_name in module_names:
            result = context.get_analysis_result(module_name)
            if result:
                # Extract summary data from result if available
                if isinstance(result, dict):
                    # Try to find summary data in the result
                    if "global_stats" in result:
                        module_data[module_name] = result["global_stats"]
                    elif "speaker_stats" in result:
                        module_data[module_name] = result["speaker_stats"]
                    else:
                        module_data[module_name] = result
                else:
                    module_data[module_name] = result

        return module_data

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save results using OutputService (new interface).

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        # Stats module saves summary text, which is handled in run_from_context
        # This method is called by the base class but stats handles saving differently
        pass


def _load_config_hash(transcript_dir: str) -> str | None:
    try:
        from pathlib import Path
        from transcriptx.core.config.persistence import (
            compute_config_hash,
            load_run_effective,
        )

        run_dir = Path(transcript_dir)
        config_payload = load_run_effective(run_dir)
        if isinstance(config_payload, dict):
            return compute_config_hash(config_payload)
    except Exception:
        return None
    return None


def _load_git_sha() -> str | None:
    try:
        from pathlib import Path

        current = Path(__file__).resolve()
        for parent in current.parents:
            git_dir = parent / ".git"
            head_path = git_dir / "HEAD"
            if head_path.exists():
                head_content = head_path.read_text(encoding="utf-8").strip()
                if head_content.startswith("ref:"):
                    ref_path = git_dir / head_content.split(" ", 1)[1]
                    if ref_path.exists():
                        return ref_path.read_text(encoding="utf-8").strip()[:12]
                return head_content[:12]
    except Exception:
        return None
    return None
