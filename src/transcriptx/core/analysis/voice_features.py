from __future__ import annotations

from typing import Any, Dict

from transcriptx.core.analysis.base import AnalysisModule  # type: ignore[import-untyped]
from transcriptx.core.output.output_service import (  # type: ignore[import-untyped]
    create_output_service,
)
from transcriptx.core.utils.logger import (  # type: ignore[import-untyped]
    get_logger,
    log_analysis_complete,
    log_analysis_error,
    log_analysis_start,
)
from transcriptx.core.utils.module_result import (  # type: ignore[import-untyped]
    build_module_result,
    capture_exception,
    now_iso,
)

from transcriptx.core.analysis.voice.extract import (  # type: ignore[import-untyped]
    load_or_compute_voice_features,
)
from transcriptx.core.analysis.voice.deps import check_voice_optional_deps  # type: ignore[import-untyped]
from transcriptx.core.utils.config import get_config  # type: ignore[import-untyped]

logger = get_logger()


class VoiceFeaturesAnalysis(AnalysisModule):
    """
    Voice feature extraction and caching module.

    This module is the *only* place that resolves audio and computes per-segment
    voice features. Downstream voice modules depend on this module and load the
    persisted feature table via the locator payload stored in PipelineContext.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.module_name = "voice_features"

    def analyze(self, segments: list[dict[str, Any]], speaker_map: Dict[str, str] | None = None) -> Dict[str, Any]:
        # Not used; this module runs via run_from_context to access transcript_path/output_dir.
        return {}

    def run_from_context(self, context: Any) -> Dict[str, Any]:
        started_at = now_iso()
        try:
            log_analysis_start(self.module_name, context.transcript_path)

            output_service = create_output_service(
                context.transcript_path,
                self.module_name,
                output_dir=context.get_transcript_dir(),
                run_id=context.get_run_id(),
                runtime_flags=context.get_runtime_flags(),
            )

            voice_cfg = getattr(getattr(get_config(), "analysis", None), "voice", None)
            egemaps_enabled = bool(getattr(voice_cfg, "egemaps_enabled", True))
            deps = check_voice_optional_deps(egemaps_enabled=egemaps_enabled)
            if not deps.get("ok"):
                payload = {
                    "status": "skipped",
                    "skipped_reason": "missing_optional_deps",
                    "missing_optional_deps": deps.get("missing_optional_deps", []),
                    "install_hint": deps.get("install_hint"),
                }
                output_service.save_data(
                    payload, "voice_features_locator", format_type="json"
                )
                try:
                    context.store_analysis_result(self.module_name, payload)
                except Exception:
                    pass
                log_analysis_complete(self.module_name, context.transcript_path)
                return build_module_result(
                    module_name=self.module_name,
                    status="success",
                    started_at=started_at,
                    finished_at=now_iso(),
                    artifacts=output_service.get_artifacts(),
                    metrics={
                        "skipped_reason": payload["skipped_reason"],
                        "missing_optional_deps": payload["missing_optional_deps"],
                    },
                    payload_type="analysis_results",
                    payload=payload,
                )

            locator = load_or_compute_voice_features(
                context=context,
                output_service=output_service,
            )

            # Persist the locator payload (small)
            output_service.save_data(locator, "voice_features_locator", format_type="json")

            # Record feature table artifacts if present (they're written directly to disk)
            for key, artifact_type in (
                ("voice_feature_core_path", "data"),
                ("voice_feature_egemaps_path", "data"),
                ("voice_feature_vad_runs_path", "data"),
                ("cache_meta_path", "json"),
            ):
                path = locator.get(key)
                if not path:
                    continue
                try:
                    output_service._record_artifact(  # type: ignore[attr-defined]
                        __import__("pathlib").Path(path),
                        artifact_type,
                    )
                except Exception:
                    pass

            # Store locator for downstream modules
            try:
                context.store_analysis_result(self.module_name, locator)
            except Exception:
                pass

            log_analysis_complete(self.module_name, context.transcript_path)
            return build_module_result(
                module_name=self.module_name,
                status="success",
                started_at=started_at,
                finished_at=now_iso(),
                artifacts=output_service.get_artifacts(),
                metrics={
                    "skipped_reason": locator.get("skipped_reason"),
                    "cache_hit": (locator.get("meta") or {}).get("cache_hit"),
                },
                payload_type="analysis_results",
                payload=dict(locator),
            )
        except Exception as exc:
            log_analysis_error(self.module_name, context.transcript_path, str(exc))
            return build_module_result(
                module_name=self.module_name,
                status="error",
                started_at=started_at,
                finished_at=now_iso(),
                artifacts=[],
                metrics={},
                payload_type="analysis_results",
                payload={},
                error=capture_exception(exc),
            )

