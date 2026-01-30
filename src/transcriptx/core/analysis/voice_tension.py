from __future__ import annotations

from typing import Any, Dict

from transcriptx.core.analysis.base import AnalysisModule  # type: ignore[import-untyped]
from transcriptx.core.output.output_service import create_output_service  # type: ignore[import-untyped]
from transcriptx.core.utils.config import get_config  # type: ignore[import-untyped]
from transcriptx.core.utils.logger import (  # type: ignore[import-untyped]
    log_analysis_complete,
    log_analysis_error,
    log_analysis_start,
)
from transcriptx.core.utils.module_result import (  # type: ignore[import-untyped]
    build_module_result,
    capture_exception,
    now_iso,
)
from transcriptx.utils.text_utils import is_named_speaker  # type: ignore[import-untyped]

from transcriptx.core.analysis.voice.aggregate import compute_arousal_raw, compute_tension_curve, robust_stats
from transcriptx.core.analysis.voice.cache import load_voice_features
from transcriptx.core.analysis.voice.charts import tension_curve_spec


class VoiceTensionAnalysis(AnalysisModule):
    """Global conversation tension curve from voice features."""

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.module_name = "voice_tension"

    def analyze(self, segments, speaker_map=None) -> Dict[str, Any]:
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

            locator = context.get_analysis_result("voice_features") or {}
            if locator.get("status") != "ok":
                skipped_reason = locator.get("skipped_reason") or "no_voice_features"
                payload = {"status": "skipped", "skipped_reason": skipped_reason}
                output_service.save_data(payload, "voice_tension_locator", format_type="json")
                log_analysis_complete(self.module_name, context.transcript_path)
                return build_module_result(
                    module_name=self.module_name,
                    status="success",
                    started_at=started_at,
                    finished_at=now_iso(),
                    artifacts=output_service.get_artifacts(),
                    metrics={"skipped_reason": skipped_reason},
                    payload_type="analysis_results",
                    payload=payload,
                )

            core_path = locator.get("voice_feature_core_path")
            eg_path = locator.get("voice_feature_egemaps_path")
            df = load_voice_features(
                core_path=__import__("pathlib").Path(core_path),
                egemaps_path=__import__("pathlib").Path(eg_path) if eg_path else None,
            )

            cfg = get_config()
            voice_cfg = getattr(getattr(cfg, "analysis", None), "voice", None)
            bin_seconds = float(getattr(voice_cfg, "bin_seconds", 30.0))
            smoothing_alpha = float(getattr(voice_cfg, "smoothing_alpha", 0.25))
            include_unnamed = bool(getattr(voice_cfg, "include_unnamed_in_global_curves", True))

            # Compute arousal per segment if missing
            if "arousal_raw" not in df.columns:
                global_stats_energy = robust_stats(df["rms_db"].astype(float).to_numpy())
                global_stats_pitch = robust_stats(df["f0_range_semitones"].astype(float).to_numpy())
                global_stats_rate = robust_stats(df["speech_rate_wps"].astype(float).to_numpy())

                arousals = []
                for _, r in df.iterrows():
                    arousals.append(
                        compute_arousal_raw(
                            rms_db=r.get("rms_db"),
                            f0_range_semitones=r.get("f0_range_semitones"),
                            speech_rate_wps=r.get("speech_rate_wps"),
                            stats_energy=global_stats_energy,
                            stats_pitch_range=global_stats_pitch,
                            stats_rate=global_stats_rate,
                        )
                    )
                df = df.assign(arousal_raw=arousals)

            if not include_unnamed and "speaker" in df.columns:
                df = df[df["speaker"].apply(lambda s: bool(s) and is_named_speaker(str(s)))]

            curve_rows = compute_tension_curve(
                df=df,
                bin_seconds=bin_seconds,
                smoothing_alpha=smoothing_alpha,
            )

            output_service.save_data(curve_rows, "voice_tension_curve", format_type="json")
            output_service.save_data(curve_rows, "voice_tension_curve", format_type="csv")

            spec = tension_curve_spec(curve_rows)
            if spec:
                output_service.save_chart(spec, chart_type="timeline")

            summary = {
                "bins": len(curve_rows),
                "bin_seconds": bin_seconds,
                "smoothing_alpha": smoothing_alpha,
            }
            output_service.save_summary(summary, {}, analysis_metadata={})

            log_analysis_complete(self.module_name, context.transcript_path)
            return build_module_result(
                module_name=self.module_name,
                status="success",
                started_at=started_at,
                finished_at=now_iso(),
                artifacts=output_service.get_artifacts(),
                metrics={"bins": len(curve_rows)},
                payload_type="analysis_results",
                payload={"summary": summary, "curve": curve_rows},
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

