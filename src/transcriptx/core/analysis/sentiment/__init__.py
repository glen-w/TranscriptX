"""
Sentiment Analysis Module for TranscriptX.

This module provides sentiment analysis using VADER or a transformers
sentiment model, with a stable normalized output contract (compound_norm,
pos_norm, neg_norm, neu_norm).
"""

import os
from collections import defaultdict
from typing import Any, Dict, List

from nltk.sentiment.vader import SentimentIntensityAnalyzer
from textblob import TextBlob

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.nlp_utils import preprocess_for_sentiment
from transcriptx.core.utils.logger import get_logger, log_info, log_warning
from transcriptx.core.utils.output import suppress_stdout_stderr, spinner
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.utils.notifications import notify_user
from transcriptx.io import save_transcript
from transcriptx.core.utils.path_utils import get_enriched_transcript_path
from transcriptx.core.utils.artifact_writer import write_csv
from transcriptx.core.utils.viz_ids import (
    VIZ_SENTIMENT_ROLLING_SPEAKER,
    VIZ_SENTIMENT_MULTI_SPEAKER_GLOBAL,
)
from transcriptx.core.viz.specs import LineTimeSeriesSpec

logger = get_logger()

_DISABLE_DOWNLOADS_ENV = "TRANSCRIPTX_DISABLE_DOWNLOADS"


def _downloads_disabled() -> bool:
    value = os.getenv(_DISABLE_DOWNLOADS_ENV, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _normalize_transformers_sentiment(
    result: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Map transformers text-classification output (e.g. positive/negative/neutral
    with scores) to the same shape as VADER: compound, pos, neg, neu in
    [-1,1] and [0,1] respectively.
    """
    if not result:
        return {
            "compound": 0.0,
            "pos": 0.0,
            "neg": 0.0,
            "neu": 1.0,
            "label": "",
            "score": 0.0,
        }
    scores_by_label: Dict[str, float] = {item["label"].lower(): float(item["score"]) for item in result}
    pos = scores_by_label.get("positive", 0.0)
    neg = scores_by_label.get("negative", 0.0)
    neu = scores_by_label.get("neutral", 0.0)
    # Normalize to sum 1 if needed (some models return logits)
    total = pos + neg + neu
    if total > 0:
        pos, neg, neu = pos / total, neg / total, neu / total
    compound = pos - neg  # in [-1, 1]
    top = max(result, key=lambda x: x["score"])
    return {
        "compound": compound,
        "pos": pos,
        "neg": neg,
        "neu": neu,
        "label": top["label"],
        "score": float(top["score"]),
    }


# Initialize the VADER sentiment analyzer with automatic resource download
def _ensure_vader_lexicon():
    """Ensure vader_lexicon is downloaded before initializing SentimentIntensityAnalyzer."""
    try:
        import nltk

        try:
            nltk.data.find("sentiment/vader_lexicon.zip")
        except LookupError:
            if _downloads_disabled():
                # CI/offline mode: do not attempt network downloads.
                raise
            # Try to notify user, but don't fail if notify_user isn't available yet
            try:
                notify_user(
                    "📥 Downloading NLTK vader_lexicon resource (required for sentiment analysis)...",
                    technical=True,
                    section="sentiment",
                )
            except Exception:
                # Fallback to print if notify_user isn't available
                print(
                    "📥 Downloading NLTK vader_lexicon resource (required for sentiment analysis)..."
                )
            nltk.download("vader_lexicon", quiet=True)
    except Exception as e:
        error_msg = (
            f"⚠️ Could not download vader_lexicon: {e}. "
            "Please run: python -c \"import nltk; nltk.download('vader_lexicon')\""
        )
        try:
            notify_user(error_msg, technical=True, section="sentiment")
        except Exception:
            print(error_msg)
        raise


_sia = None


def _get_sia() -> SentimentIntensityAnalyzer:
    global _sia
    if _sia is None:
        _ensure_vader_lexicon()
        _sia = SentimentIntensityAnalyzer()
    return _sia


def _score_sentiment_textblob(text: str) -> Dict[str, float]:
    """
    Offline-safe sentiment fallback based on TextBlob polarity.

    Returns the same VADER-like shape (compound, pos, neu, neg).
    """
    blob = TextBlob(text)
    polarity = float(getattr(blob.sentiment, "polarity", 0.0))
    compound = max(-1.0, min(1.0, polarity))
    pos = max(0.0, compound)
    neg = max(0.0, -compound)
    neu = max(0.0, 1.0 - pos - neg)
    return {"compound": compound, "pos": pos, "neu": neu, "neg": neg}


def _load_sentiment_transformers(model_name: str):
    """Load transformers sentiment pipeline. Returns None on failure."""
    try:
        from transcriptx.core.utils.lazy_imports import get_transformers

        with suppress_stdout_stderr(), spinner("Loading sentiment model…"):
            transformers = get_transformers()
            pipe = transformers.pipeline(
                "text-classification",
                model=model_name,
                top_k=None,
            )
        log_info("SENTIMENT", "Transformers sentiment model loaded successfully")
        return pipe
    except Exception as e:
        log_warning("SENTIMENT", f"Could not load transformers sentiment model: {e}")
        try:
            notify_user(
                "Could not load transformers sentiment model.",
                technical=True,
                section="sentiment",
            )
        except Exception:
            pass
        return None


def score_sentiment(text: str, preprocess: bool = False) -> dict:
    """
    Calculate sentiment scores for a given text using VADER.

    This is a utility function used by other analysis modules.

    Args:
        text: The text to analyze for sentiment
        preprocess: Whether to preprocess text to remove tics before analysis

    Returns:
        Dictionary containing sentiment scores with keys:
        - compound: Overall sentiment score (-1 to +1)
        - pos: Positive sentiment score (0 to 1)
        - neg: Negative sentiment score (0 to 1)
        - neu: Neutral sentiment score (0 to 1)
    """
    if preprocess:
        text = preprocess_for_sentiment(text)
        if not text:
            return {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0}
    try:
        return _get_sia().polarity_scores(text)
    except Exception:
        return _score_sentiment_textblob(text)


class SentimentAnalysis(AnalysisModule):
    """
    Sentiment analysis module using VADER sentiment analyzer.

    This module analyzes sentiment for each segment and provides:
    - Per-segment sentiment scores
    - Per-speaker sentiment analysis
    - Multi-speaker sentiment comparison
    - Rolling sentiment plots
    - Data export in JSON and CSV formats
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the sentiment analysis module."""
        super().__init__(config)
        self.module_name = "sentiment"
        from transcriptx.core.utils.config import get_config

        cfg = get_config().analysis
        self.sentiment_backend = getattr(cfg, "sentiment_backend", "vader")
        self.sentiment_model_name = getattr(
            cfg,
            "sentiment_model_name",
            "cardiffnlp/twitter-roberta-base-sentiment-latest",
        )
        self.sia = None
        self._transformers_pipe = None
        if self.sentiment_backend == "vader":
            try:
                _ensure_vader_lexicon()
                self.sia = _get_sia()
            except Exception:
                # Offline-safe fallback.
                self.sentiment_backend = "textblob"
        else:
            self._transformers_pipe = _load_sentiment_transformers(
                self.sentiment_model_name
            )
            if self._transformers_pipe is None:
                try:
                    _ensure_vader_lexicon()
                    self.sia = _get_sia()
                    self.sentiment_backend = "vader"
                    logger.warning("SENTIMENT falling back to VADER")
                except Exception:
                    self.sentiment_backend = "textblob"
                    logger.warning("SENTIMENT falling back to TextBlob")

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Perform sentiment analysis on transcript segments.

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility)

        Returns:
            Dictionary containing sentiment analysis results
        """
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        # Calculate sentiment scores for each segment; set raw + normalized
        for seg in segments:
            text = seg.get("text", "")
            raw = self._score_sentiment(text)
            seg["sentiment"] = raw
            seg["sentiment_backend"] = self.sentiment_backend
            seg["sentiment_compound_norm"] = raw.get("compound", 0.0)
            seg["sentiment_pos_norm"] = raw.get("pos", 0.0)
            seg["sentiment_neg_norm"] = raw.get("neg", 0.0)
            seg["sentiment_neu_norm"] = raw.get("neu", 0.0)
            if self.sentiment_backend == "transformers" and "label" in raw:
                seg["sentiment_label"] = raw.get("label", "")
                seg["sentiment_score"] = raw.get("score", 0.0)
            else:
                seg["sentiment_label"] = ""
                seg["sentiment_score"] = 0.0

        # Group segments by speaker for analysis
        speaker_segments = defaultdict(list)
        all_rows = []

        for seg in segments:
            speaker_info = extract_speaker_info(seg)
            if speaker_info is None:
                continue
            speaker = get_speaker_display_name(
                speaker_info.grouping_key, [seg], segments
            )

            # Skip unnamed speakers
            if not speaker or not self._is_named_speaker(speaker):
                continue

            speaker_segments[speaker].append(seg)

            # Prepare data for export
            sentiment = seg.get("sentiment", {})
            row = {
                "speaker": speaker,
                "start": seg.get("start", 0),
                "text": seg.get("text", ""),
                "compound": sentiment.get("compound"),
                "pos": sentiment.get("pos"),
                "neu": sentiment.get("neu"),
                "neg": sentiment.get("neg"),
            }
            all_rows.append(row)

        # Generate per-speaker analysis
        speaker_analysis = {}
        for speaker, segs in speaker_segments.items():
            speaker_analysis[speaker] = self._analyze_speaker_sentiment(segs, speaker)

        # Generate multi-speaker comparison
        multi_speaker_data = self._generate_multi_speaker_data(speaker_segments)

        # Generate global stats
        if all_rows:
            compound_values = [
                r["compound"] for r in all_rows if r["compound"] is not None
            ]
            pos_values = [r["pos"] for r in all_rows if r["pos"] is not None]
            neu_values = [r["neu"] for r in all_rows if r["neu"] is not None]
            neg_values = [r["neg"] for r in all_rows if r["neg"] is not None]

            global_stats = {
                "count": len(all_rows),
                "compound_mean": (
                    sum(compound_values) / len(compound_values)
                    if compound_values
                    else 0
                ),
                "pos_mean": sum(pos_values) / len(pos_values) if pos_values else 0,
                "neu_mean": sum(neu_values) / len(neu_values) if neu_values else 0,
                "neg_mean": sum(neg_values) / len(neg_values) if neg_values else 0,
            }
        else:
            global_stats = {}

        # Convert speaker_analysis to speaker_stats format for compatibility
        speaker_stats = {}
        for speaker, analysis in speaker_analysis.items():
            speaker_stats[speaker] = {
                "count": analysis.get("total_segments", 0),
                "compound_mean": analysis.get("average_compound", 0),
                "pos_mean": 0,  # Not calculated in current implementation
                "neu_mean": 0,  # Not calculated in current implementation
                "neg_mean": 0,  # Not calculated in current implementation
            }

        return {
            "segments_with_sentiment": segments,
            "speaker_segments": dict(
                speaker_segments
            ),  # For compatibility with _save_results
            "speaker_analysis": speaker_analysis,
            "speaker_stats": speaker_stats,  # For compatibility with _save_results
            "multi_speaker_data": multi_speaker_data,
            "all_rows": all_rows,
            "global_stats": global_stats,  # For compatibility with _save_results
            "speaker_map": speaker_map,  # For compatibility with _save_results
            "summary": {
                "total_segments": len(segments),
                "total_speakers": len(speaker_segments),
                "analysis_timestamp": self._get_timestamp(),
            },
        }

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save results using OutputService (new interface).

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        segments = results["segments_with_sentiment"]
        speaker_segments = results["speaker_segments"]
        all_rows = results["all_rows"]
        speaker_map = results["speaker_map"]
        base_name = output_service.base_name

        # Save enriched transcript with sentiment scores
        enriched_path = get_enriched_transcript_path(
            output_service.transcript_path, "sentiment"
        )
        os.makedirs(os.path.dirname(enriched_path), exist_ok=True)
        save_transcript(segments, enriched_path)

        # Save complete transcript-wide sentiment data
        output_service.save_data(all_rows, "sentiment", format_type="json")
        output_service.save_data(all_rows, "sentiment", format_type="csv")

        # Generate per-speaker analysis and visualizations
        for speaker, segs in speaker_segments.items():
            spec = self._build_rolling_sentiment_spec(segs, speaker)
            if spec:
                output_service.save_chart(spec)

            # Prepare speaker data for export
            speaker_data = [
                {
                    "start": s.get("start", 0),
                    "text": s.get("text", ""),
                    **s.get("sentiment", {}),
                }
                for s in segs
            ]

            # Save speaker data
            output_service.save_data(
                speaker_data,
                f"{speaker}_sentiment",
                format_type="json",
                subdirectory="speakers",
            )
            output_service.save_data(
                speaker_data,
                f"{speaker}_sentiment",
                format_type="csv",
                subdirectory="speakers",
            )

        # Generate multi-speaker comparison plot only when more than one identified speaker
        named_speakers = [s for s in speaker_segments if is_named_speaker(s)]
        if len(named_speakers) > 1:
            multi_spec = self._build_multi_speaker_sentiment_spec(speaker_segments)
            if multi_spec:
                output_service.save_chart(multi_spec)

        # Save summary
        output_service.save_summary(
            results["global_stats"], results["speaker_stats"], analysis_metadata={}
        )

    def _score_sentiment(self, text: str, preprocess: bool = False) -> Dict[str, Any]:
        """Calculate sentiment scores; VADER or transformers, same normalized shape."""
        if not text or not text.strip():
            return {"compound": 0.0, "pos": 0.0, "neu": 1.0, "neg": 0.0}

        if preprocess:
            text = preprocess_for_sentiment(text)
            if not text:
                return {"compound": 0.0, "pos": 0.0, "neu": 1.0, "neg": 0.0}

        if self.sentiment_backend == "transformers" and self._transformers_pipe:
            raw = self._transformers_pipe(text)[0]
            return _normalize_transformers_sentiment(raw)
        if self.sentiment_backend == "textblob" or self.sia is None:
            return _score_sentiment_textblob(text)
        scores = self.sia.polarity_scores(text)
        return {
            "compound": scores["compound"],
            "pos": scores["pos"],
            "neu": scores["neu"],
            "neg": scores["neg"],
        }

    def _is_named_speaker(self, speaker: str) -> bool:
        """Check if speaker is named (not a system ID)."""
        return is_named_speaker(speaker)

    def _analyze_speaker_sentiment(
        self, segments: List[Dict[str, Any]], speaker: str
    ) -> Dict[str, Any]:
        """Analyze sentiment for a specific speaker."""
        if not segments:
            return {}

        sentiments = [seg.get("sentiment", {}) for seg in segments]
        compound_scores = [s.get("compound", 0) for s in sentiments]

        return {
            "speaker": speaker,
            "total_segments": len(segments),
            "average_compound": sum(compound_scores) / len(compound_scores),
            "sentiment_distribution": {
                "positive": len([s for s in compound_scores if s > 0.05]),
                "neutral": len([s for s in compound_scores if -0.05 <= s <= 0.05]),
                "negative": len([s for s in compound_scores if s < -0.05]),
            },
            "sentiment_trend": compound_scores,
        }

    def _generate_multi_speaker_data(
        self, speaker_segments: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Generate multi-speaker sentiment comparison data."""
        comparison_data = {}

        for speaker, segments in speaker_segments.items():
            sentiments = [seg.get("sentiment", {}) for seg in segments]
            compound_scores = [s.get("compound", 0) for s in sentiments]

            comparison_data[speaker] = {
                "average_sentiment": (
                    sum(compound_scores) / len(compound_scores)
                    if compound_scores
                    else 0
                ),
                "sentiment_variance": self._calculate_variance(compound_scores),
                "total_segments": len(segments),
            }

        return comparison_data

    def _calculate_variance(self, scores: List[float]) -> float:
        """Calculate variance of sentiment scores."""
        if len(scores) < 2:
            return 0.0

        mean = sum(scores) / len(scores)
        variance = sum((x - mean) ** 2 for x in scores) / len(scores)
        return variance

    def _save_csv_data(
        self,
        rows: List[Dict[str, Any]],
        output_structure: Dict[str, str],
        base_name: str,
    ) -> None:
        """Save sentiment data as CSV."""
        csv_path = os.path.join(
            output_structure["data_dir"], f"{base_name}_sentiment_data.csv"
        )

        fieldnames = ["speaker", "start", "text", "compound", "pos", "neu", "neg"]
        csv_rows = [[row.get(field) for field in fieldnames] for row in rows]
        write_csv(csv_path, csv_rows, header=fieldnames)

    def _build_rolling_sentiment_spec(
        self, segments: List[Dict], speaker_name: str
    ) -> LineTimeSeriesSpec | None:
        x_vals: list[float] = []
        y_vals: list[float] = []
        for seg in segments:
            sentiment = seg.get("sentiment", {})
            compound = sentiment.get("compound")
            if compound is None:
                continue
            x_vals.append(seg.get("start", 0) / 60.0)
            y_vals.append(compound)
        if not y_vals:
            return None
        return LineTimeSeriesSpec(
            viz_id=VIZ_SENTIMENT_ROLLING_SPEAKER,
            module=self.module_name,
            name="rolling_sentiment",
            scope="speaker",
            speaker=speaker_name,
            chart_intent="line_timeseries",
            title=f"Rolling Sentiment: {speaker_name}",
            x_label="Time (minutes)",
            y_label="Compound Sentiment Score",
            markers=True,
            series=[{"name": speaker_name, "x": x_vals, "y": y_vals}],
        )

    def _build_multi_speaker_sentiment_spec(
        self, speaker_segments: Dict[str, List[Dict[str, Any]]]
    ) -> LineTimeSeriesSpec | None:
        series: list[dict[str, Any]] = []
        for speaker, segs in speaker_segments.items():
            x_vals = []
            y_vals = []
            for seg in segs:
                sentiment = seg.get("sentiment", {})
                compound = sentiment.get("compound")
                if compound is None:
                    continue
                x_vals.append(seg.get("start", 0) / 60.0)
                y_vals.append(compound)
            if y_vals:
                series.append({"name": speaker, "x": x_vals, "y": y_vals})
        if not series:
            return None
        return LineTimeSeriesSpec(
            viz_id=VIZ_SENTIMENT_MULTI_SPEAKER_GLOBAL,
            module=self.module_name,
            name="multi_speaker_sentiment",
            scope="global",
            chart_intent="line_timeseries",
            title="Multi-Speaker Sentiment",
            x_label="Time (minutes)",
            y_label="Compound Sentiment Score",
            markers=False,
            series=series,
        )

    def _get_timestamp(self) -> str:
        """Get current timestamp for analysis metadata."""
        from datetime import datetime

        return datetime.now().isoformat()
