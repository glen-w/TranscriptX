from __future__ import annotations

from typing import Any, Dict, cast


from transcriptx.core.analysis.base import AnalysisModule  # type: ignore[import-untyped]
from transcriptx.core.analysis.sentiment import score_sentiment  # type: ignore[import-untyped]
from transcriptx.core.output.output_service import create_output_service  # type: ignore[import-untyped]
from transcriptx.core.utils.config import get_config  # type: ignore[import-untyped]
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
from transcriptx.utils.text_utils import is_named_speaker  # type: ignore[import-untyped]

from transcriptx.core.analysis.voice.aggregate import (  # type: ignore[import-untyped]
    compute_arousal_raw,
    compute_mismatch_score,
    compute_valence_proxy,
    robust_stats,
)
from transcriptx.core.analysis.voice.cache import load_voice_features  # type: ignore[import-untyped]
from transcriptx.core.analysis.voice.charts import (  # type: ignore[import-untyped]
    mismatch_scatter_spec,
    mismatch_timeline_spec,
)

logger = get_logger()


class VoiceMismatchAnalysis(AnalysisModule):
    """Tone–Text mismatch detector (\"sarcasm/discord\" moments)."""

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.module_name = "voice_mismatch"

    def analyze(
        self,
        segments: list[dict[str, Any]],
        speaker_map: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
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
                    payload, "voice_mismatch_locator", format_type="json"
                )
                log_analysis_complete(self.module_name, context.transcript_path)
                return cast(
                    Dict[str, Any],
                    build_module_result(
                        module_name=self.module_name,
                        status="success",
                        started_at=started_at,
                        finished_at=now_iso(),
                        artifacts=output_service.get_artifacts(),
                        metrics={"skipped_reason": skipped_reason},
                        payload_type="analysis_results",
                        payload=payload,
                    ),
                )

            core_path = locator.get("voice_feature_core_path")
            eg_path = locator.get("voice_feature_egemaps_path")
            if not core_path:
                raise RuntimeError("voice_features locator missing core path")

            df = load_voice_features(
                core_path=__import__("pathlib").Path(core_path),
                egemaps_path=__import__("pathlib").Path(eg_path) if eg_path else None,
            )

            segments = context.get_segments()
            transcript_key = context.get_transcript_key()

            # Build per-segment text + sentiment map keyed by segment_id
            from transcriptx.core.analysis.voice.schema import (  # type: ignore[import-untyped]
                resolve_segment_id,
            )

            seg_rows: list[dict[str, Any]] = []
            for seg in segments:
                seg_id = resolve_segment_id(seg, transcript_key)
                speaker = seg.get("speaker")
                text = seg.get("text", "") or ""
                sent = seg.get("sentiment", {}) or {}
                compound = sent.get("compound")
                if compound is None:
                    compound = score_sentiment(text).get("compound", 0.0)
                seg_rows.append(
                    {
                        "segment_id": seg_id,
                        "text": text,
                        "vader_compound": float(compound),
                        "speaker": speaker,
                    }
                )

            pd = __import__("pandas")
            seg_df = pd.DataFrame(seg_rows)
            work = df.merge(
                seg_df[["segment_id", "text", "vader_compound"]],
                on="segment_id",
                how="left",
            )

            cfg = get_config()
            voice_cfg = getattr(getattr(cfg, "analysis", None), "voice", None)
            mismatch_threshold = float(getattr(voice_cfg, "mismatch_threshold", 0.6))
            top_k = int(getattr(voice_cfg, "top_k_moments", 30))
            include_unnamed = bool(
                getattr(voice_cfg, "include_unnamed_in_global_curves", True)
            )

            # Compute global baseline (fallback for unnamed speakers)
            global_stats_energy = robust_stats(work["rms_db"].astype(float).to_numpy())
            global_stats_pitch = robust_stats(
                work["f0_range_semitones"].astype(float).to_numpy()
            )
            global_stats_rate = robust_stats(
                work["speech_rate_wps"].astype(float).to_numpy()
            )

            # Optional egemaps stats if columns exist
            has_hnr = "eg_hnr_db" in work.columns
            has_jitter = "eg_jitter" in work.columns
            has_shimmer = "eg_shimmer_db" in work.columns
            has_alpha = "eg_alpha_ratio" in work.columns

            # Per-speaker baselines
            speaker_stats: dict[str, dict[str, dict[str, float]]] = {}
            speaker_eg_stats: dict[str, dict[str, dict[str, float]]] = {}
            for spk, g in work.groupby("speaker"):
                if spk is None:
                    continue
                speaker_stats[str(spk)] = {
                    "energy": robust_stats(g["rms_db"].astype(float).to_numpy()),
                    "pitch": robust_stats(
                        g["f0_range_semitones"].astype(float).to_numpy()
                    ),
                    "rate": robust_stats(g["speech_rate_wps"].astype(float).to_numpy()),
                }
                if has_hnr and has_jitter and has_shimmer and has_alpha:
                    speaker_eg_stats[str(spk)] = {
                        "hnr": robust_stats(g["eg_hnr_db"].astype(float).to_numpy()),
                        "jitter": robust_stats(g["eg_jitter"].astype(float).to_numpy()),
                        "shimmer": robust_stats(
                            g["eg_shimmer_db"].astype(float).to_numpy()
                        ),
                        "alpha": robust_stats(
                            g["eg_alpha_ratio"].astype(float).to_numpy()
                        ),
                    }

            # Compute arousal/valence/mismatch per row
            arousals: list[float] = []
            valences: list[float | None] = []
            mismatch_scores: list[float] = []

            for _, r in work.iterrows():
                spk = r.get("speaker")
                spk_key = "" if spk is None else str(spk)
                stats = speaker_stats.get(spk_key)
                if stats is None:
                    stats_energy, stats_pitch, stats_rate = (
                        global_stats_energy,
                        global_stats_pitch,
                        global_stats_rate,
                    )
                else:
                    stats_energy, stats_pitch, stats_rate = (
                        stats["energy"],
                        stats["pitch"],
                        stats["rate"],
                    )

                arousal = compute_arousal_raw(
                    rms_db=r.get("rms_db"),
                    f0_range_semitones=r.get("f0_range_semitones"),
                    speech_rate_wps=r.get("speech_rate_wps"),
                    stats_energy=stats_energy,
                    stats_pitch_range=stats_pitch,
                    stats_rate=stats_rate,
                )
                arousals.append(arousal)

                # Prefer deep-mode valence if present in cached features.
                valence = r.get("valence_raw")
                if valence is None:
                    eg = {}
                    for col in (
                        "eg_hnr_db",
                        "eg_jitter",
                        "eg_shimmer_db",
                        "eg_alpha_ratio",
                    ):
                        if col in work.columns and r.get(col) is not None:
                            eg[col.removeprefix("eg_")] = float(r.get(col))

                    eg_stats = speaker_eg_stats.get(spk_key)
                    if eg_stats is not None:
                        valence = compute_valence_proxy(
                            eg=eg,
                            stats_hnr=eg_stats.get("hnr"),
                            stats_jitter=eg_stats.get("jitter"),
                            stats_shimmer=eg_stats.get("shimmer"),
                            stats_alpha=eg_stats.get("alpha"),
                        )
                valences.append(valence)

                vader = float(r.get("vader_compound") or 0.0)
                mismatch_scores.append(
                    compute_mismatch_score(
                        vader_compound=vader,
                        arousal_raw=arousal,
                        valence_raw=valence,
                    )
                )

            work = work.assign(
                arousal_raw=arousals,
                valence_raw=valences,
                mismatch_score=mismatch_scores,
            )

            # Ranked moments table (exclude unnamed speakers by default)
            ranked = work.copy()
            ranked["speaker_is_named"] = ranked["speaker"].apply(
                lambda s: bool(s) and is_named_speaker(str(s))
            )
            ranked_table = ranked[ranked["speaker_is_named"]].copy()
            ranked_table = ranked_table[
                ranked_table["mismatch_score"] >= mismatch_threshold
            ]
            ranked_table = ranked_table.sort_values(
                "mismatch_score", ascending=False
            ).head(top_k)

            moments: list[dict[str, Any]] = []
            for rank, (_, row) in enumerate(ranked_table.iterrows(), start=1):
                moments.append(
                    {
                        "rank": rank,
                        "segment_id": row.get("segment_id"),
                        "speaker": row.get("speaker"),
                        "start_s": float(row.get("start_s", 0.0)),
                        "end_s": float(row.get("end_s", 0.0)),
                        "vader_compound": float(row.get("vader_compound", 0.0)),
                        "arousal_raw": float(row.get("arousal_raw", 0.0)),
                        "valence_raw": row.get("valence_raw"),
                        "mismatch_score": float(row.get("mismatch_score", 0.0)),
                        "text": (row.get("text") or "")[:500],
                    }
                )

            output_service.save_data(
                moments, "voice_mismatch_moments", format_type="json"
            )
            output_service.save_data(
                moments, "voice_mismatch_moments", format_type="csv"
            )

            # Global scatter points (optionally include unnamed)
            curve_df = work if include_unnamed else work[work["speaker_is_named"]]
            points = []
            for _, row in curve_df.iterrows():
                points.append(
                    {
                        "sentiment": float(row.get("vader_compound", 0.0)),
                        "arousal": float(row.get("arousal_raw", 0.0)),
                        "hover": f"{row.get('speaker')}: {str(row.get('text') or '')[:80]}",
                    }
                )

            spec = mismatch_scatter_spec(points)
            if spec:
                output_service.save_chart(spec, chart_type="scatter")

            tl_rows = [
                {
                    "start_s": float(row.get("start_s", 0.0)),
                    "mismatch_score": float(row.get("mismatch_score", 0.0)),
                }
                for _, row in curve_df.sort_values("start_s").iterrows()
            ]
            tl_spec = mismatch_timeline_spec(tl_rows)
            if tl_spec:
                output_service.save_chart(tl_spec, chart_type="timeline")

            summary = {
                "moments_count": len(moments),
                "threshold": mismatch_threshold,
                "top_k": top_k,
                "valence_method": (
                    "deep_model"
                    if (
                        "deep_emotion_label" in work.columns
                        and work["deep_emotion_label"].notna().any()
                    )
                    else (
                        "egemaps_proxy"
                        if (has_hnr and has_jitter and has_shimmer and has_alpha)
                        else "none"
                    )
                ),
            }
            output_service.save_summary(summary, {}, analysis_metadata={})

            log_analysis_complete(self.module_name, context.transcript_path)
            return cast(
                Dict[str, Any],
                build_module_result(
                    module_name=self.module_name,
                    status="success",
                    started_at=started_at,
                    finished_at=now_iso(),
                    artifacts=output_service.get_artifacts(),
                    metrics={"moments_count": len(moments)},
                    payload_type="analysis_results",
                    payload={"summary": summary, "moments": moments},
                ),
            )
        except Exception as exc:
            log_analysis_error(self.module_name, context.transcript_path, str(exc))
            return cast(
                Dict[str, Any],
                build_module_result(
                    module_name=self.module_name,
                    status="error",
                    started_at=started_at,
                    finished_at=now_iso(),
                    artifacts=[],
                    metrics={},
                    payload_type="analysis_results",
                    payload={},
                    error=capture_exception(exc),
                ),
            )
