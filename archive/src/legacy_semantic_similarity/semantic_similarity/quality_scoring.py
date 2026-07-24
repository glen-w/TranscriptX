"""
Quality scoring and segment filtering logic.
"""

from __future__ import annotations

from typing import Any

from transcriptx.core.utils.logger import log_error, log_warning


class BasicQualityScorer:
    """Quality scoring based on configurable indicators."""

    def __init__(self, config: Any, log_tag: str) -> None:
        self.config = config
        self.log_tag = log_tag

    def filter_segments(
        self, segments: list[dict[str, Any]], max_segments: int
    ) -> list[dict[str, Any]]:
        if len(segments) <= max_segments:
            return segments

        config = self.config.get_quality_filtering_config()
        weights = config["weights"]
        thresholds = config["thresholds"]
        indicators = config["indicators"]

        scored_segments: list[tuple[float, int, dict[str, Any]]] = []
        for i, seg in enumerate(segments):
            text = seg.get("text", "").strip()
            if not text or len(text.split()) < thresholds.get("min_words", 3):
                continue

            score = 0.0
            word_count = len(text.split())
            optimal_range = thresholds.get("optimal_word_range", (5, 50))
            good_range = thresholds.get("good_word_range", (3, 100))

            if optimal_range[0] <= word_count <= optimal_range[1]:
                score += weights.get("length_optimal", 3.0)
            elif good_range[0] <= word_count <= good_range[1]:
                score += weights.get("length_good", 1.0)

            complex_reasoning_words = indicators.get("complex_reasoning", [])
            if any(word in text.lower() for word in complex_reasoning_words):
                score += weights.get("complex_reasoning", 2.0)

            opinions_ideas_words = indicators.get("opinions_ideas", [])
            if any(word in text.lower() for word in opinions_ideas_words):
                score += weights.get("opinions_ideas", 2.0)

            agreement_words = indicators.get("agreement_disagreement", [])
            if any(word in text.lower() for word in agreement_words):
                score += weights.get("agreement_disagreement", 1.0)

            filler_words = indicators.get("filler_words", [])
            filler_count = sum(text.lower().count(word) for word in filler_words)
            score += filler_count * weights.get("filler_penalty", -0.5)

            if i > 0:
                prev_text = segments[i - 1].get("text", "").strip()
                if text.lower() == prev_text.lower():
                    score += weights.get("exact_repetition_penalty", -5.0)
                else:
                    overlap_threshold = thresholds.get("overlap_threshold", 0.7)
                    word_overlap = len(
                        set(text.split()) & set(prev_text.split())
                    ) / len(text.split())
                    if word_overlap > overlap_threshold:
                        score += weights.get("high_overlap_penalty", -3.0)

            scored_segments.append((score, i, seg))

        scored_segments.sort(key=lambda x: x[0], reverse=True)
        selected_indices = [idx for _, idx, _ in scored_segments[:max_segments]]
        selected_indices.sort()
        return [segments[i] for i in selected_indices]


class AdvancedQualityScorer:
    """Quality scoring using integrated analysis results."""

    def __init__(self, config: Any, log_tag: str) -> None:
        self.config = config
        self.log_tag = log_tag

    def calculate_quality_score(
        self, segment: dict[str, Any], analysis_results: dict[str, Any]
    ) -> float:
        try:
            score = 0.0
            text = segment.get("text", "").lower()

            length_score = min(len(text.split()) / 20.0, 1.0)
            score += length_score * 0.2

            if "sentiment" in analysis_results:
                try:
                    sentiment_data = analysis_results["sentiment"]
                    if "speaker_data" in sentiment_data:
                        speaker = segment.get("speaker", "")
                        if speaker in sentiment_data["speaker_data"]:
                            speaker_sentiment = sentiment_data["speaker_data"][speaker]
                            if "average_sentiment" in speaker_sentiment:
                                sentiment_score = abs(
                                    speaker_sentiment["average_sentiment"]
                                )
                                score += sentiment_score * 0.15
                except Exception as exc:
                    log_warning(self.log_tag, f"Sentiment integration failed: {exc}")

            if "emotion" in analysis_results:
                try:
                    emotion_data = analysis_results["emotion"]
                    if "speaker_data" in emotion_data:
                        speaker = segment.get("speaker", "")
                        if speaker in emotion_data["speaker_data"]:
                            speaker_emotion = emotion_data["speaker_data"][speaker]
                            if "emotion_scores" in speaker_emotion:
                                emotion_scores = speaker_emotion["emotion_scores"]
                                max_emotion = (
                                    max(emotion_scores.values())
                                    if emotion_scores
                                    else 0
                                )
                                score += max_emotion * 0.15
                except Exception as exc:
                    log_warning(self.log_tag, f"Emotion integration failed: {exc}")

            if "acts" in analysis_results:
                try:
                    acts_data = analysis_results["acts"]
                    if "speaker_data" in acts_data:
                        speaker = segment.get("speaker", "")
                        if speaker in acts_data["speaker_data"]:
                            speaker_acts = acts_data["speaker_data"][speaker]
                            if "act_distribution" in speaker_acts:
                                act_dist = speaker_acts["act_distribution"]
                                informative_score = act_dist.get(
                                    "inform", 0
                                ) + act_dist.get("elaborate", 0)
                                score += informative_score * 0.1
                except Exception as exc:
                    log_warning(self.log_tag, f"Acts integration failed: {exc}")

            if "tics" in analysis_results:
                try:
                    tics_data = analysis_results["tics"]
                    if "speaker_data" in tics_data:
                        speaker = segment.get("speaker", "")
                        if speaker in tics_data["speaker_data"]:
                            speaker_tics = tics_data["speaker_data"][speaker]
                            if "tic_ratio" in speaker_tics:
                                tic_penalty = speaker_tics["tic_ratio"] * 0.2
                                score = max(0, score - tic_penalty)
                except Exception as exc:
                    log_warning(self.log_tag, f"Tics integration failed: {exc}")

            if "understandability" in analysis_results:
                try:
                    understandability_data = analysis_results["understandability"]
                    if "speaker_data" in understandability_data:
                        speaker = segment.get("speaker", "")
                        if speaker in understandability_data["speaker_data"]:
                            speaker_understandability = understandability_data[
                                "speaker_data"
                            ][speaker]
                            if "average_readability" in speaker_understandability:
                                readability_score = (
                                    speaker_understandability["average_readability"]
                                    / 100.0
                                )
                                score += readability_score * 0.1
                except Exception as exc:
                    log_warning(
                        self.log_tag, f"Understandability integration failed: {exc}"
                    )

            quality_indicators = [
                "because",
                "therefore",
                "however",
                "although",
                "nevertheless",
                "furthermore",
                "moreover",
                "consequently",
                "thus",
                "hence",
                "agree",
                "disagree",
                "think",
                "believe",
                "opinion",
                "view",
                "important",
                "significant",
                "crucial",
                "essential",
                "key",
            ]

            keyword_score = sum(1 for word in quality_indicators if word in text) / len(
                quality_indicators
            )
            score += keyword_score * 0.2

            return min(score, 1.0)
        except Exception as exc:
            log_warning(self.log_tag, f"Quality scoring failed: {exc}")
            return 0.5

    def filter_segments(
        self,
        segments: list[dict[str, Any]],
        max_segments: int,
        analysis_results: dict[str, Any],
    ) -> list[dict[str, Any]]:
        try:
            if len(segments) <= max_segments:
                return segments

            scored_segments: list[tuple[dict[str, Any], float]] = []
            for segment in segments:
                quality_score = self.calculate_quality_score(segment, analysis_results)
                scored_segments.append((segment, quality_score))

            scored_segments.sort(key=lambda x: x[1], reverse=True)
            filtered_segments = [
                segment for segment, score in scored_segments[:max_segments]
            ]

            return filtered_segments
        except Exception as exc:
            log_error(
                self.log_tag,
                f"Advanced quality filtering failed: {exc}",
                exception=exc,
            )
            return segments[:max_segments]
