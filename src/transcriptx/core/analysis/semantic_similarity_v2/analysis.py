"""AnalysisModule wrapper for semantic_similarity_v2."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.semantic_similarity_v2.config_resolve import (
    resolve_semantic_similarity_v2_runtime,
)
from transcriptx.core.analysis.semantic_similarity_v2.output import with_schema
from transcriptx.core.analysis.semantic_similarity_v2.pipeline import (
    run_semantic_similarity_v2_pipeline,
)
from transcriptx.core.analysis.semantic_similarity_v2.visualization import (
    create_visualizations_v2,
)
from transcriptx.core.utils.module_result import build_module_result, now_iso
from transcriptx.core.utils.speaker_extraction import count_named_speakers


class SemanticSimilarityV2Analysis(AnalysisModule):
    """Semantic similarity v2 (batched embeddings, vectorized similarity)."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self.module_name = "semantic_similarity_v2"
        self._pending_v2_diag: Any = None

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        raise RuntimeError("Use run_from_context for semantic_similarity_v2")

    def _modules_in_run_from_context(self, context: Any) -> Set[str]:
        present: set[str] = set()
        for m in ("sentiment", "emotion", "acts"):
            try:
                if context.get_analysis_result(m) is not None:
                    present.add(m)
            except Exception:
                continue
        return present

    def run_from_context(self, context: Any) -> Dict[str, Any]:
        from transcriptx.core.output.output_service import create_output_service
        from transcriptx.core.utils.config import get_config
        from transcriptx.core.utils.logger import (
            log_error,
            log_analysis_complete,
            log_analysis_start,
        )

        segments = context.get_segments()
        if count_named_speakers(segments) <= 1:
            log_analysis_start(self.module_name, context.transcript_path)
            context.store_analysis_result(self.module_name, {})
            log_analysis_complete(self.module_name, context.transcript_path)
            return build_module_result(
                module_name=self.module_name,
                status="success",
                started_at=now_iso(),
                finished_at=now_iso(),
                artifacts=[],
                metrics={
                    "skipped": True,
                    "reason": "single_identified_speaker",
                    "schema_version": "semantic_similarity_v2.1",
                },
                payload_type="analysis_results",
                payload={},
            )

        started_at = now_iso()
        log_analysis_start(self.module_name, context.transcript_path)

        analysis = get_config().analysis
        modules_in_run = self._modules_in_run_from_context(context)
        try:
            v2_cfg, resolve_diag = resolve_semantic_similarity_v2_runtime(
                analysis,
                modules_in_run=modules_in_run,
            )
        except Exception as exc:
            finished_at = now_iso()
            log_analysis_complete(self.module_name, context.transcript_path)
            return build_module_result(
                module_name=self.module_name,
                status="error",
                started_at=started_at,
                finished_at=finished_at,
                artifacts=[],
                metrics={"reason": str(exc)},
                payload_type="analysis_results",
                payload={},
            )

        try:
            results, diag = run_semantic_similarity_v2_pipeline(
                segments,
                v2_cfg,
                resolve_diagnostics=resolve_diag,
            )
        except ImportError:
            finished_at = now_iso()
            log_analysis_complete(self.module_name, context.transcript_path)
            return build_module_result(
                module_name=self.module_name,
                status="blocked",
                started_at=started_at,
                finished_at=finished_at,
                artifacts=[],
                metrics={"reason": "missing_dependency:torch"},
                payload_type="analysis_results",
                payload={},
            )
        except Exception as exc:
            finished_at = now_iso()
            log_error(
                "SEMANTIC_V2",
                f"semantic_similarity_v2 failed: {exc}",
                exception=exc,
            )
            log_analysis_complete(self.module_name, context.transcript_path)
            return build_module_result(
                module_name=self.module_name,
                status="error",
                started_at=started_at,
                finished_at=finished_at,
                artifacts=[],
                metrics={
                    "reason": str(exc),
                    "exception_type": type(exc).__name__,
                    "schema_version": "semantic_similarity_v2.1",
                },
                payload_type="analysis_results",
                payload={},
            )

        output_service = create_output_service(
            context.transcript_path,
            self.module_name,
            output_dir=context.get_transcript_dir(),
            run_id=context.get_run_id(),
            runtime_flags=context.get_runtime_flags(),
        )
        self._pending_v2_diag = diag
        self.save_results(results, output_service)
        self._pending_v2_diag = None
        context.store_analysis_result(self.module_name, results)
        log_analysis_complete(self.module_name, context.transcript_path)
        finished_at = now_iso()
        duration = float(diag.runtime_seconds_breakdown.get("total", 0.0))
        return build_module_result(
            module_name=self.module_name,
            status="success",
            started_at=started_at,
            finished_at=finished_at,
            artifacts=output_service.get_artifacts(),
            metrics={
                "duration_seconds": duration,
                "schema_version": "semantic_similarity_v2.1",
                **diag.to_dict(),
            },
            payload_type="analysis_results",
            payload=results,
        )

    def _save_results(self, results: Dict[str, Any], output_service: Any) -> None:
        diag = self._pending_v2_diag
        assert diag is not None
        output_service.save_data(
            with_schema(results),
            "semantic_similarity_v2_repetitions",
            format_type="json",
        )
        output_service.save_data(
            with_schema(diag.to_dict()),
            "semantic_similarity_v2_diagnostics",
            format_type="json",
        )
        output_service.save_data(
            with_schema(results.get("clustering", {})),
            "semantic_similarity_v2_clusters",
            format_type="json",
        )
        try:
            create_visualizations_v2(
                results,
                output_service,
                output_service.base_name,
                "SEMANTIC_V2",
            )
        except Exception as exc:
            from transcriptx.core.utils.logger import log_warning

            log_warning("SEMANTIC_V2", f"Failed to create visualizations: {exc}")

        global_stats = {
            "total_repetitions": int(results.get("total_repetitions", 0)),
            "unique_patterns": int(results.get("unique_patterns", 0)),
            "schema_version": "semantic_similarity_v2.1",
        }
        output_service.save_summary(
            global_stats,
            {},
            analysis_metadata=with_schema({"mode": results.get("mode", "basic")}),
        )
