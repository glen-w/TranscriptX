from __future__ import annotations

from typing import Any, Dict

import numpy as np

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

from transcriptx.core.analysis.voice.aggregate import robust_stats, robust_z
from transcriptx.core.analysis.voice.cache import load_voice_features
from transcriptx.core.analysis.voice.charts import drift_timeline_spec


class VoiceFingerprintAnalysis(AnalysisModule):
    """Per-speaker vocal fingerprint baseline + drift moments."""

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.module_name = "voice_fingerprint"

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
                output_service.save_data(
                    payload, "voice_fingerprint_locator", format_type="json"
                )
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
            drift_threshold = float(getattr(voice_cfg, "drift_threshold", 2.5))
            top_k = int(getattr(voice_cfg, "top_k_moments", 30))

            # Compute per-speaker baseline and drift scores
            fingerprints: dict[str, Any] = {}
            drift_moments: dict[str, list[dict[str, Any]]] = {}

            for speaker, g in df.groupby("speaker"):
                if not speaker or not is_named_speaker(str(speaker)):
                    continue
                g = g.copy()
                stats_energy = robust_stats(g["rms_db"].astype(float).to_numpy())
                stats_pitch = robust_stats(
                    g["f0_range_semitones"].astype(float).to_numpy()
                )
                stats_rate = robust_stats(g["speech_rate_wps"].astype(float).to_numpy())

                fingerprints[str(speaker)] = {
                    "speaker": str(speaker),
                    "n_segments": int(len(g)),
                    "baseline": {
                        "rms_db": stats_energy,
                        "f0_range_semitones": stats_pitch,
                        "speech_rate_wps": stats_rate,
                    },
                }

                # Drift score per segment (max abs robust z)
                z_energy = g["rms_db"].apply(
                    lambda x: abs(
                        robust_z(
                            x,
                            median=stats_energy["median"],
                            sigma=stats_energy["sigma"],
                        )
                    )
                )
                z_pitch = g["f0_range_semitones"].apply(
                    lambda x: abs(
                        robust_z(
                            x, median=stats_pitch["median"], sigma=stats_pitch["sigma"]
                        )
                    )
                )
                z_rate = g["speech_rate_wps"].apply(
                    lambda x: abs(
                        robust_z(
                            x, median=stats_rate["median"], sigma=stats_rate["sigma"]
                        )
                    )
                )
                drift_score = np.maximum.reduce(
                    [z_energy.to_numpy(), z_pitch.to_numpy(), z_rate.to_numpy()]
                )
                g = g.assign(drift_score=drift_score)

                # Save per-speaker timeline chart (full series)
                series_rows = [
                    {
                        "start_s": float(row.get("start_s", 0.0)),
                        "drift_score": float(row.get("drift_score", 0.0)),
                    }
                    for _, row in g.sort_values("start_s").iterrows()
                ]
                spec = drift_timeline_spec(str(speaker), series_rows)
                if spec:
                    output_service.save_chart(spec, chart_type="timeline")

                # Drift moments (top K above threshold)
                candidates = g[g["drift_score"] >= drift_threshold].sort_values(
                    "drift_score", ascending=False
                )
                candidates = candidates.head(top_k)
                moments: list[dict[str, Any]] = []
                for rank, (_, row) in enumerate(candidates.iterrows(), start=1):
                    moments.append(
                        {
                            "rank": rank,
                            "segment_id": row.get("segment_id"),
                            "start_s": float(row.get("start_s", 0.0)),
                            "end_s": float(row.get("end_s", 0.0)),
                            "drift_score": float(row.get("drift_score", 0.0)),
                            "rms_db": row.get("rms_db"),
                            "f0_range_semitones": row.get("f0_range_semitones"),
                            "speech_rate_wps": row.get("speech_rate_wps"),
                        }
                    )
                drift_moments[str(speaker)] = moments

                # Save per-speaker artifacts
                output_service.save_data(
                    fingerprints[str(speaker)],
                    f"{speaker}_voice_fingerprint",
                    format_type="json",
                    subdirectory="speakers",
                    speaker=str(speaker),
                )
                output_service.save_data(
                    moments,
                    f"{speaker}_voice_drift_moments",
                    format_type="json",
                    subdirectory="speakers",
                    speaker=str(speaker),
                )
                output_service.save_data(
                    moments,
                    f"{speaker}_voice_drift_moments",
                    format_type="csv",
                    subdirectory="speakers",
                    speaker=str(speaker),
                )

            summary = {
                "speakers": len(fingerprints),
                "drift_threshold": drift_threshold,
                "top_k": top_k,
            }
            output_service.save_summary(summary, {}, analysis_metadata={})

            log_analysis_complete(self.module_name, context.transcript_path)
            return build_module_result(
                module_name=self.module_name,
                status="success",
                started_at=started_at,
                finished_at=now_iso(),
                artifacts=output_service.get_artifacts(),
                metrics={"speakers": len(fingerprints)},
                payload_type="analysis_results",
                payload={
                    "summary": summary,
                    "fingerprints": fingerprints,
                    "drift_moments": drift_moments,
                },
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
