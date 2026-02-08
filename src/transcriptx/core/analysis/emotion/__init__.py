"""
Emotion Detection Module for TranscriptX.

This module provides comprehensive emotion detection and analysis capabilities
for transcript segments, including emotion classification, intensity analysis,
and temporal emotion tracking.
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Dict, List

import numpy as np

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.config import EMOTION_CATEGORIES
from transcriptx.core.utils.logger import get_logger, log_info, log_warning
from transcriptx.core.utils.downloads import downloads_disabled
from transcriptx.core.utils.output import suppress_stdout_stderr, spinner
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.utils.notifications import notify_user
from transcriptx.io import save_transcript
from transcriptx.core.utils.path_utils import get_enriched_transcript_path
from transcriptx.core.utils.viz_ids import (
    VIZ_EMOTION_RADAR_SPEAKER,
    VIZ_EMOTION_RADAR_GLOBAL,
)
from transcriptx.core.viz.specs import BarCategoricalSpec

logger = get_logger()

# Initialize NRCLex with automatic resource download
def _ensure_textblob_corpora():
    """Ensure TextBlob corpora are downloaded before initializing NRCLex."""
    try:
        if downloads_disabled():
            raise RuntimeError("Downloads disabled (TRANSCRIPTX_DISABLE_DOWNLOADS)")
        from textblob.download_corpora import download_all

        try:
            notify_user(
                "📥 Downloading TextBlob corpora (required for emotion analysis)...",
                technical=True,
                section="emotion",
            )
        except Exception:
            # Fallback to print if notify_user isn't available yet
            print("📥 Downloading TextBlob corpora (required for emotion analysis)...")
        download_all()
    except Exception as e:
        error_msg = (
            f"⚠️ Could not download TextBlob corpora: {e}. "
            "Please run: python -m textblob.download_corpora"
        )
        try:
            notify_user(error_msg, technical=True, section="emotion")
        except Exception:
            print(error_msg)
        raise


def _load_nrclex():
    try:
        from nrclex import NRCLex

        _ = NRCLex("test").raw_emotion_scores
        log_info("EMOTION", "NRCLex loaded successfully")
        return NRCLex
    except Exception as e:
        try:
            log_warning("EMOTION", f"NRCLex not available or missing corpus: {e}")
            _ensure_textblob_corpora()
            from nrclex import NRCLex

            _ = NRCLex("test").raw_emotion_scores
            log_info("EMOTION", "NRCLex loaded successfully after downloading corpora")
            return NRCLex
        except Exception as retry_error:
            log_warning(
                "EMOTION", f"NRCLex not available after corpus download: {retry_error}"
            )
            try:
                notify_user(
                    "⚠️ NRCLex not available. Emotion analysis may be limited.",
                    technical=True,
                    section="emotion",
                )
            except Exception:
                print("⚠️ NRCLex not available. Emotion analysis may be limited.")
            return None


def _load_emotion_model(model_name: str | None = None):
    try:
        if downloads_disabled():
            log_warning("EMOTION", "Downloads disabled; skipping contextual emotion model load")
            return None
        from transcriptx.core.utils.lazy_imports import get_transformers

        if model_name is None:
            from transcriptx.core.utils.config import get_config

            config = get_config()
            model_name = getattr(
                config.analysis,
                "emotion_model_name",
                "bhadresh-savani/distilbert-base-uncased-emotion",
            )

        with suppress_stdout_stderr(), spinner("🔮 Loading contextual emotion model..."):
            transformers = get_transformers()
            emotion_model = transformers.pipeline(
                "text-classification",
                model=model_name,
                top_k=None,
            )
        log_info("EMOTION", "Contextual emotion model loaded successfully")
        return emotion_model
    except Exception as e:
        log_warning("EMOTION", f"Could not load contextual emotion model: {e}")
        try:
            notify_user(
                "⚠️ Could not load contextual emotion model.",
                technical=True,
                section="emotion",
            )
        except Exception:
            print("⚠️ Could not load contextual emotion model.")
        return None


class EmotionAnalysis(AnalysisModule):
    """
    Emotion detection and analysis module.

    This module analyzes emotions in transcript segments using both NRC lexicon
    and transformer-based contextual emotion models.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the emotion analysis module."""
        super().__init__(config)
        self.module_name = "emotion"
        self.nrclex = _load_nrclex()
        from transcriptx.core.utils.config import get_config

        cfg = get_config().analysis
        model_name = getattr(
            cfg,
            "emotion_model_name",
            "bhadresh-savani/distilbert-base-uncased-emotion",
        )
        self.emotion_model = _load_emotion_model(model_name)
        self.emotion_output_mode = getattr(cfg, "emotion_output_mode", "top1")
        self.emotion_score_threshold = float(
            getattr(cfg, "emotion_score_threshold", 0.30)
        )

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Perform emotion analysis on transcript segments (pure logic, no I/O).

        Uses database-driven speaker identification. speaker_map parameter is deprecated.

        Args:
            segments: List of transcript segments (should have speaker_db_id for proper identification)
            speaker_map: Deprecated - Speaker ID to name mapping (kept for backward compatibility only)

        Returns:
            Dictionary containing emotion analysis results
        """
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        nrc_scores = defaultdict(lambda: defaultdict(float))
        contextual_all, contextual_examples = self._compute_contextual_emotions(
            segments
        )

        # Compute NRC emotions for each segment; set context_emotion_* from NRC if no HF
        for seg in segments:
            speaker_info = extract_speaker_info(seg)
            if speaker_info is None:
                continue
            speaker = get_speaker_display_name(
                speaker_info.grouping_key, [seg], segments
            )
            if not speaker or not is_named_speaker(speaker):
                continue
            text = seg.get("text", "")
            scores = self._compute_nrc_emotions(text)
            seg["nrc_emotion"] = scores
            for emo, val in scores.items():
                nrc_scores[speaker][emo] += val
            # If no HF contextual result, set context_emotion_* from NRC
            if seg.get("context_emotion_source") is None and scores:
                primary_nrc = max(scores, key=scores.get)
                seg["context_emotion_primary"] = primary_nrc
                seg["context_emotion_scores"] = dict(scores)
                seg["context_emotion_source"] = "nrc"
                seg["context_emotion"] = primary_nrc  # backward compat
            elif seg.get("context_emotion_source") is None:
                seg["context_emotion_primary"] = ""
                seg["context_emotion_scores"] = {}
                seg["context_emotion_source"] = "none"
                seg["context_emotion"] = ""  # backward compat

        # Normalize scores
        for speaker in nrc_scores:
            total = sum(nrc_scores[speaker].values())
            if total > 0:
                for emo in nrc_scores[speaker]:
                    nrc_scores[speaker][emo] /= total

        # Prepare combined rows for export
        combined_rows = []
        for speaker, scores in nrc_scores.items():
            if not is_named_speaker(speaker):
                continue
            row = {"speaker": speaker}
            row.update(scores)
            combined_rows.append(row)

        # Aggregate global stats
        all_scores = defaultdict(float)
        for speaker_scores in nrc_scores.values():
            for emo, val in speaker_scores.items():
                all_scores[emo] += val
        total = sum(all_scores.values())
        if total:
            for emo in all_scores:
                all_scores[emo] /= total

        speaker_stats = {
            speaker: dict(scores)
            for speaker, scores in nrc_scores.items()
            if is_named_speaker(speaker)
        }

        # Ensure every segment has context_emotion_primary/scores/source
        for seg in segments:
            if "context_emotion_source" not in seg:
                seg["context_emotion_primary"] = ""
                seg["context_emotion_scores"] = {}
                seg["context_emotion_source"] = "none"
                seg["context_emotion"] = ""  # backward compat

        # Count segments with emotion data for logging
        segments_with_emotion_count = 0
        segments_with_nrc_count = 0
        segments_with_context_count = 0
        for seg in segments:
            if "nrc_emotion" in seg:
                segments_with_nrc_count += 1
                nrc_data = seg.get("nrc_emotion", {})
                if (
                    isinstance(nrc_data, dict)
                    and nrc_data
                    and any(v > 0 for v in nrc_data.values())
                ):
                    segments_with_emotion_count += 1
            if seg.get("context_emotion_source") == "hf" or (
                seg.get("context_emotion_primary")
            ):
                segments_with_context_count += 1
                segments_with_emotion_count += 1

        logger.debug(
            f"[EMOTION] Analysis complete: {len(segments)} total segments, "
            f"{segments_with_nrc_count} with nrc_emotion, "
            f"{segments_with_context_count} with context_emotion, "
            f"{segments_with_emotion_count} with any emotion data"
        )

        result = {
            "segments_with_emotion": segments,
            "nrc_scores": dict(nrc_scores),
            "combined_rows": combined_rows,
            "contextual_all": contextual_all,
            "contextual_examples": contextual_examples,
            "all_scores": dict(all_scores),
            "speaker_stats": speaker_stats,
            "global_stats": dict(all_scores),
        }
        # Backward-compatible keys for tests/legacy consumers
        result["segments"] = segments
        result["emotions"] = dict(all_scores)
        return result

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save results using OutputService (new interface).

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        from transcriptx.core.utils.lazy_imports import get_matplotlib_pyplot

        segments = results["segments_with_emotion"]
        nrc_scores = results["nrc_scores"]
        combined_rows = results["combined_rows"]
        contextual_all = results["contextual_all"]
        contextual_examples = results["contextual_examples"]
        all_scores = results["all_scores"]
        base_name = output_service.base_name
        plt = get_matplotlib_pyplot()

        # Save enriched transcript
        enriched_path = get_enriched_transcript_path(
            output_service.transcript_path, "emotion"
        )
        os.makedirs(os.path.dirname(enriched_path), exist_ok=True)
        save_transcript(segments, enriched_path)

        # Save global data
        output_service.save_data(nrc_scores, "nrc_emotion_scores", format_type="json")
        output_service.save_data(combined_rows, "nrc_emotion_scores", format_type="csv")
        output_service.save_data(
            contextual_all, "contextual_emotion_labels", format_type="json"
        )
        output_service.save_data(
            contextual_examples, "contextual_emotion_examples", format_type="json"
        )

        # Save per-speaker data and charts
        for speaker, scores in nrc_scores.items():
            speaker_safe = speaker.replace(" ", "_")

            # Save speaker data
            output_service.save_data(
                scores,
                f"{speaker_safe}_nrc_emotion",
                format_type="json",
                subdirectory="speakers",
                speaker=speaker,
            )

            # Save CSV
            csv_data = [[k, v] for k, v in scores.items()]
            output_service.save_data(
                csv_data,
                f"{speaker_safe}_nrc_emotion",
                format_type="csv",
                subdirectory="speakers",
                speaker=speaker,
            )

            if scores:
                spec = BarCategoricalSpec(
                    viz_id=VIZ_EMOTION_RADAR_SPEAKER,
                    module=self.module_name,
                    name="radar",
                    scope="speaker",
                    speaker=speaker,
                    chart_intent="bar_categorical",
                    title=f"Emotion Profile: {speaker}",
                    x_label="Emotion",
                    y_label="Score",
                    categories=list(scores.keys()),
                    values=list(scores.values()),
                )
                output_service.save_chart(spec, chart_type="radar")

                radar_fig = self._create_emotion_radar(speaker, scores)
                if radar_fig:
                    output_service.save_chart(
                        chart_id="emotion_radar_polar",
                        scope="speaker",
                        speaker=speaker,
                        static_fig=radar_fig,
                        chart_type="radar_polar",
                        viz_id=f"emotion.radar_polar.speaker.{speaker_safe}",
                        title=f"Emotion Profile: {speaker}",
                    )
                    plt.close(radar_fig)

        # Create and save global radar chart only when more than one identified speaker
        named_speakers = [s for s in nrc_scores if is_named_speaker(s)]
        if all_scores and len(named_speakers) > 1:
            spec = BarCategoricalSpec(
                viz_id=VIZ_EMOTION_RADAR_GLOBAL,
                module=self.module_name,
                name="emotion_all_radar",
                scope="global",
                chart_intent="bar_categorical",
                title="Emotion Profile: All Speakers",
                x_label="Emotion",
                y_label="Score",
                categories=list(all_scores.keys()),
                values=list(all_scores.values()),
            )
            output_service.save_chart(spec, chart_type="radar")
            radar_fig = self._create_emotion_radar("All Speakers", all_scores, True)
            if radar_fig:
                output_service.save_chart(
                    chart_id="emotion_radar_polar",
                    scope="global",
                    static_fig=radar_fig,
                    chart_type="radar_polar",
                    viz_id="emotion.radar_polar.global",
                    title="Emotion Profile: All Speakers",
                )
                plt.close(radar_fig)

        # Save summary
        output_service.save_summary(
            results["global_stats"], results["speaker_stats"], analysis_metadata={}
        )

    def _compute_nrc_emotions(self, text: str) -> dict:
        """Compute NRC emotions for text."""
        if not self.nrclex:
            return {}
        emo = self.nrclex(text)
        total = sum(emo.raw_emotion_scores.values())
        return (
            {k: v / total for k, v in emo.raw_emotion_scores.items()}
            if total > 0
            else {}
        )

    def _parse_pipeline_emotion_result(
        self, result: List[Dict[str, Any]]
    ) -> tuple[str, Dict[str, float]]:
        """
        Parse pipeline output (single-label or multi-label) into primary label and
        scores dict. Does not depend on model ID; behavior is driven by
        emotion_output_mode and emotion_score_threshold.
        """
        if not result:
            return "", {}
        scores_dict: Dict[str, float] = {
            item["label"]: float(item["score"]) for item in result
        }
        if not scores_dict:
            return "", {}
        primary = max(scores_dict, key=scores_dict.get)
        if self.emotion_output_mode == "multilabel":
            threshold = self.emotion_score_threshold
            scores_dict = {
                k: v for k, v in scores_dict.items() if v >= threshold
            }
        else:
            # top1: keep only primary score (or all for optional storage)
            scores_dict = {primary: scores_dict[primary]}
        return primary, scores_dict

    def _compute_contextual_emotions(self, segments: List[Dict]):
        """Compute contextual emotions using transformer model."""
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        if not self.emotion_model:
            return {}, {}
        contextual_emotions = defaultdict(list)
        emotion_examples = defaultdict(lambda: defaultdict(list))

        for segment in segments:
            speaker_info = extract_speaker_info(segment)
            if speaker_info is None:
                continue
            speaker = get_speaker_display_name(
                speaker_info.grouping_key, [segment], segments
            )
            if not is_named_speaker(speaker):
                continue
            text = segment.get("text", "").strip()
            if not text:
                continue
            raw = self.emotion_model(text)[0]
            primary, scores_dict = self._parse_pipeline_emotion_result(raw)
            segment["context_emotion_primary"] = primary
            segment["context_emotion_scores"] = scores_dict
            segment["context_emotion_source"] = "hf"
            segment["context_emotion"] = primary  # backward compat
            if primary:
                contextual_emotions[speaker].append(primary)
                emotion_examples[speaker][primary].append(
                    (scores_dict.get(primary, 0.0), text)
                )

        return contextual_emotions, emotion_examples

    def _create_emotion_radar(
        self, speaker: str, scores: dict, is_global: bool = False
    ):
        """Create emotion radar chart."""
        from transcriptx.core.utils.lazy_imports import get_matplotlib_pyplot

        categories = EMOTION_CATEGORIES
        values = [scores.get(cat, 0) * 100 for cat in categories]
        values += values[:1]
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]

        plt = get_matplotlib_pyplot()
        fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
        ax.plot(angles, values, linewidth=2)
        ax.fill(angles, values, alpha=0.25)
        ax.set_yticklabels([])
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=10)
        ax.set_title(f"Emotion Profile: {speaker}", size=14, pad=20)
        plt.tight_layout()

        return fig


def compute_nrc_emotions(text: str) -> dict:
    """Compute NRC emotions for text."""
    nrclex = _load_nrclex()
    if not nrclex:
        return {}
    emo = nrclex(text)
    total = sum(emo.raw_emotion_scores.values())
    return (
        {k: v / total for k, v in emo.raw_emotion_scores.items()} if total > 0 else {}
    )
