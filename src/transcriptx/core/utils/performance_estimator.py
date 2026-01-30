"""
Performance estimation system for TranscriptX.

This module provides time estimation capabilities based on historical performance logs.
It analyzes past execution data to predict future operation durations.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class PerformanceEstimator:
    """
    Estimates execution time based on historical performance logs.
    """

    def __init__(self, logger_instance=None):
        """
        Initialize the performance estimator.

        Args:
            logger_instance: Optional logger instance (uses global if not provided)
        """
        if logger_instance is None:
            from transcriptx.core.utils.performance_logger import get_performance_logger

            self.logger = get_performance_logger()
        else:
            self.logger = logger_instance
        self.default_lookback_days = 30

    def _query_spans(
        self,
        name: str,
        start_date: datetime,
        attributes_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        from transcriptx.database import get_session
        from transcriptx.database.repositories import PerformanceSpanRepository

        session = get_session()
        try:
            repo = PerformanceSpanRepository(session)
            spans = repo.query_spans(
                name=name,
                start_date=start_date,
                status_code="OK",
                attributes_filter=attributes_filter,
            )
            return spans
        finally:
            session.close()

    @staticmethod
    def _duration_seconds(span) -> Optional[float]:
        if span.duration_ms is not None:
            return span.duration_ms / 1000.0
        if span.start_time and span.end_time:
            return (span.end_time - span.start_time).total_seconds()
        return None

    @staticmethod
    def _percentile(values: List[float], percentile: float) -> Optional[float]:
        if not values:
            return None
        values = sorted(values)
        if percentile <= 0:
            return values[0]
        if percentile >= 100:
            return values[-1]
        k = (len(values) - 1) * (percentile / 100.0)
        f = int(k)
        c = min(f + 1, len(values) - 1)
        if f == c:
            return values[f]
        d0 = values[f] * (c - k)
        d1 = values[c] * (k - f)
        return d0 + d1

    def estimate_transcription_time(
        self,
        audio_duration_seconds: Optional[float] = None,
        file_size_mb: Optional[float] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Estimate WhisperX transcription time based on historical data.

        Args:
            audio_duration_seconds: Audio duration in seconds
            file_size_mb: File size in MB (used if duration not available)
            model: Model name for filtering (optional)

        Returns:
            Dictionary with estimated_seconds, min_seconds, max_seconds, confidence
        """
        # Get historical spans
        start_date = datetime.now() - timedelta(days=self.default_lookback_days)
        logs = self._query_spans(
            name="transcribe.whisperx",
            start_date=start_date,
            attributes_filter={"model": model} if model else None,
        )

        if not logs:
            # No historical data - provide rough estimate
            # WhisperX on CPU typically takes 10-30x real-time
            # Use conservative 20x multiplier for CPU transcription
            if audio_duration_seconds:
                # Estimate: 20 minutes per minute of audio (20x real-time)
                estimated = audio_duration_seconds * 20.0
                return {
                    "estimated_seconds": estimated,
                    "min_seconds": estimated * 0.5,  # 10x real-time (optimistic)
                    "max_seconds": estimated * 1.5,  # 30x real-time (pessimistic)
                    "confidence": "low",
                }
            elif file_size_mb:
                # Rough estimate based on file size
                # Assume ~1 MB per minute of audio (typical MP3 at 128kbps)
                # Then apply 20x real-time multiplier
                estimated_minutes_per_mb = 1.0  # 1 minute of audio per MB
                estimated_seconds_per_mb = (
                    estimated_minutes_per_mb * 60 * 20
                )  # 20x real-time
                estimated = file_size_mb * estimated_seconds_per_mb
                return {
                    "estimated_seconds": estimated,
                    "min_seconds": estimated * 0.5,  # 10x real-time
                    "max_seconds": estimated * 1.5,  # 30x real-time
                    "confidence": "low",
                }
            else:
                return {
                    "estimated_seconds": None,
                    "min_seconds": None,
                    "max_seconds": None,
                    "confidence": "none",
                }

        # Calculate rates (duration per minute of audio or per MB)
        rates = []
        for log in logs:
            metadata = log.attributes_json or {}
            duration = self._duration_seconds(log) or 0

            if audio_duration_seconds and metadata.get("audio_duration_seconds"):
                # Calculate rate: seconds per minute of audio
                audio_minutes = metadata["audio_duration_seconds"] / 60.0
                if audio_minutes > 0:
                    rate = duration / audio_minutes
                    rates.append(rate)
            elif file_size_mb and metadata.get("file_size_mb"):
                # Calculate rate: seconds per MB
                file_mb = metadata["file_size_mb"]
                if file_mb > 0:
                    rate = duration / file_mb
                    rates.append(rate)

        if not rates:
            # Fallback: use average duration if available
            durations = [
                self._duration_seconds(log)
                for log in logs
                if self._duration_seconds(log) is not None
            ]
            if durations and any(d > 0 for d in durations):
                # We have some duration data, use it
                avg_duration = sum(durations) / len(durations)
                return {
                    "estimated_seconds": avg_duration,
                    "min_seconds": min(durations),
                    "max_seconds": max(durations),
                    "p90_seconds": self._percentile(durations, 90),
                    "p95_seconds": self._percentile(durations, 95),
                    "confidence": "low",
                }
            # No useful duration data in logs - fall back to hardcoded estimate
            # (same as when there are no logs at all)
            if audio_duration_seconds:
                # Estimate: 20 minutes per minute of audio (20x real-time)
                estimated = audio_duration_seconds * 20.0
                return {
                    "estimated_seconds": estimated,
                    "min_seconds": estimated * 0.5,  # 10x real-time (optimistic)
                    "max_seconds": estimated * 1.5,  # 30x real-time (pessimistic)
                    "confidence": "low",
                }
            elif file_size_mb:
                # Rough estimate based on file size
                # Assume ~1 MB per minute of audio (typical MP3 at 128kbps)
                # Then apply 20x real-time multiplier
                estimated_minutes_per_mb = 1.0  # 1 minute of audio per MB
                estimated_seconds_per_mb = (
                    estimated_minutes_per_mb * 60 * 20
                )  # 20x real-time
                estimated = file_size_mb * estimated_seconds_per_mb
                return {
                    "estimated_seconds": estimated,
                    "min_seconds": estimated * 0.5,  # 10x real-time
                    "max_seconds": estimated * 1.5,  # 30x real-time
                    "confidence": "low",
                }
            return {
                "estimated_seconds": None,
                "min_seconds": None,
                "max_seconds": None,
                "confidence": "none",
            }

        # Calculate statistics
        median_rate = self._percentile(rates, 50) or 0
        min_rate = self._percentile(rates, 10) or 0
        max_rate = self._percentile(rates, 90) or 0

        # Use median for estimate, p10/p90 for bounds
        if audio_duration_seconds:
            estimated = (audio_duration_seconds / 60.0) * median_rate
            min_est = (audio_duration_seconds / 60.0) * min_rate
            max_est = (audio_duration_seconds / 60.0) * max_rate
            p95_est = (audio_duration_seconds / 60.0) * (
                self._percentile(rates, 95) or max_rate
            )
        elif file_size_mb:
            estimated = file_size_mb * median_rate
            min_est = file_size_mb * min_rate
            max_est = file_size_mb * max_rate
            p95_est = file_size_mb * (self._percentile(rates, 95) or max_rate)
        else:
            return {
                "estimated_seconds": None,
                "min_seconds": None,
                "max_seconds": None,
                "confidence": "none",
            }

        # Determine confidence based on sample size
        confidence = (
            "high" if len(rates) >= 10 else "medium" if len(rates) >= 5 else "low"
        )

        return {
            "estimated_seconds": round(estimated, 2),
            "min_seconds": round(min_est, 2),
            "max_seconds": round(max_est, 2),
            "p90_seconds": round(max_est, 2),
            "p95_seconds": round(p95_est, 2),
            "confidence": confidence,
        }

    def estimate_conversion_time(
        self, file_size_mb: float, bitrate: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Estimate WAV to MP3 conversion time based on historical data.

        Args:
            file_size_mb: Input file size in MB
            bitrate: MP3 bitrate (optional, for filtering)

        Returns:
            Dictionary with estimated_seconds, min_seconds, max_seconds, confidence
        """
        # Get historical spans
        start_date = datetime.now() - timedelta(days=self.default_lookback_days)
        logs = self._query_spans(
            name="audio.convert.wav_to_mp3",
            start_date=start_date,
            attributes_filter={"bitrate": bitrate} if bitrate else None,
        )

        if not logs:
            # Rough estimate: 0.5 seconds per MB
            estimated = file_size_mb * 0.5
            return {
                "estimated_seconds": estimated,
                "min_seconds": estimated * 0.5,
                "max_seconds": estimated * 2.0,
                "confidence": "low",
            }

        # Calculate rates (seconds per MB)
        rates = []
        for log in logs:
            metadata = log.attributes_json or {}
            duration = self._duration_seconds(log) or 0
            input_size = metadata.get("input_file_size_mb")

            if input_size and input_size > 0:
                rate = duration / input_size
                rates.append(rate)

        if not rates:
            # Fallback: use average duration
            durations = [self._duration_seconds(log) or 0 for log in logs]
            if durations:
                avg_duration = sum(durations) / len(durations)
                return {
                    "estimated_seconds": avg_duration,
                    "min_seconds": min(durations),
                    "max_seconds": max(durations),
                    "p90_seconds": self._percentile(durations, 90),
                    "p95_seconds": self._percentile(durations, 95),
                    "confidence": "low",
                }
            return {
                "estimated_seconds": file_size_mb * 0.5,
                "min_seconds": file_size_mb * 0.25,
                "max_seconds": file_size_mb * 1.0,
                "confidence": "low",
            }

        # Calculate statistics
        median_rate = self._percentile(rates, 50) or 0
        min_rate = self._percentile(rates, 10) or 0
        max_rate = self._percentile(rates, 90) or 0

        estimated = file_size_mb * median_rate
        min_est = file_size_mb * min_rate
        max_est = file_size_mb * max_rate

        # Determine confidence
        confidence = (
            "high" if len(rates) >= 10 else "medium" if len(rates) >= 5 else "low"
        )

        p95_est = file_size_mb * (self._percentile(rates, 95) or max_rate)

        return {
            "estimated_seconds": round(estimated, 2),
            "min_seconds": round(min_est, 2),
            "max_seconds": round(max_est, 2),
            "p90_seconds": round(max_est, 2),
            "p95_seconds": round(p95_est, 2),
            "confidence": confidence,
        }

    def estimate_compression_time(
        self, total_size_mb: float, file_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Estimate WAV compression time based on historical data.

        Args:
            total_size_mb: Total size of files to compress in MB
            file_count: Number of files to compress (optional, for filtering)

        Returns:
            Dictionary with estimated_seconds, min_seconds, max_seconds, confidence
        """
        # Get historical spans
        start_date = datetime.now() - timedelta(days=self.default_lookback_days)
        logs = self._query_spans(
            name="audio.compress.wav",
            start_date=start_date,
        )

        if not logs:
            # Rough estimate: 0.3 seconds per MB (compression is faster than conversion)
            estimated = total_size_mb * 0.3
            return {
                "estimated_seconds": estimated,
                "min_seconds": estimated * 0.5,
                "max_seconds": estimated * 2.0,
                "confidence": "low",
            }

        # Calculate rates (seconds per MB)
        rates = []
        for log in logs:
            metadata = log.attributes_json or {}
            duration = self._duration_seconds(log) or 0
            total_size = metadata.get("total_size_mb")

            if total_size and total_size > 0:
                rate = duration / total_size
                rates.append(rate)

        if not rates:
            # Fallback: use average duration
            durations = [self._duration_seconds(log) or 0 for log in logs]
            if durations:
                avg_duration = sum(durations) / len(durations)
                return {
                    "estimated_seconds": avg_duration,
                    "min_seconds": min(durations),
                    "max_seconds": max(durations),
                    "p90_seconds": self._percentile(durations, 90),
                    "p95_seconds": self._percentile(durations, 95),
                    "confidence": "low",
                }
            return {
                "estimated_seconds": total_size_mb * 0.3,
                "min_seconds": total_size_mb * 0.15,
                "max_seconds": total_size_mb * 0.6,
                "confidence": "low",
            }

        # Calculate statistics
        median_rate = self._percentile(rates, 50) or 0
        min_rate = self._percentile(rates, 10) or 0
        max_rate = self._percentile(rates, 90) or 0

        estimated = total_size_mb * median_rate
        min_est = total_size_mb * min_rate
        max_est = total_size_mb * max_rate

        # Determine confidence
        confidence = (
            "high" if len(rates) >= 10 else "medium" if len(rates) >= 5 else "low"
        )

        p95_est = total_size_mb * (self._percentile(rates, 95) or max_rate)

        return {
            "estimated_seconds": round(estimated, 2),
            "min_seconds": round(min_est, 2),
            "max_seconds": round(max_est, 2),
            "p90_seconds": round(max_est, 2),
            "p95_seconds": round(p95_est, 2),
            "confidence": confidence,
        }

    def estimate_analysis_time(
        self,
        module_name: str,
        transcript_segments: Optional[int] = None,
        transcript_words: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Estimate analysis module execution time based on historical data.

        Args:
            module_name: Name of the analysis module
            transcript_segments: Number of segments in transcript (optional)
            transcript_words: Number of words in transcript (optional)

        Returns:
            Dictionary with estimated_seconds, min_seconds, max_seconds, confidence
        """
        # Get historical spans
        start_date = datetime.now() - timedelta(days=self.default_lookback_days)
        logs = self._query_spans(
            name=f"module.{module_name}.run",
            start_date=start_date,
            attributes_filter={"module_name": module_name},
        )

        if not logs:
            # No historical data for this module
            return {
                "estimated_seconds": None,
                "min_seconds": None,
                "max_seconds": None,
                "confidence": "none",
            }

        # If we have transcript size info, try to calculate rate
        if transcript_segments or transcript_words:
            rates = []
            for log in logs:
                metadata = log.attributes_json or {}
                duration = self._duration_seconds(log) or 0

                if transcript_segments and metadata.get("transcript_segments_count"):
                    seg_count = metadata["transcript_segments_count"]
                    if seg_count > 0:
                        rate = duration / seg_count
                        rates.append(rate)
                elif transcript_words and metadata.get("transcript_word_count"):
                    word_count = metadata["transcript_word_count"]
                    if word_count > 0:
                        rate = duration / word_count
                        rates.append(rate)

            if rates:
                median_rate = self._percentile(rates, 50) or 0
                min_rate = self._percentile(rates, 10) or 0
                max_rate = self._percentile(rates, 90) or 0

                if transcript_segments:
                    estimated = transcript_segments * median_rate
                    min_est = transcript_segments * min_rate
                    max_est = transcript_segments * max_rate
                    p95_est = transcript_segments * (
                        self._percentile(rates, 95) or max_rate
                    )
                else:
                    estimated = transcript_words * median_rate
                    min_est = transcript_words * min_rate
                    max_est = transcript_words * max_rate
                    p95_est = transcript_words * (
                        self._percentile(rates, 95) or max_rate
                    )

                confidence = (
                    "high"
                    if len(rates) >= 10
                    else "medium" if len(rates) >= 5 else "low"
                )

                return {
                    "estimated_seconds": round(estimated, 2),
                    "min_seconds": round(min_est, 2),
                    "max_seconds": round(max_est, 2),
                    "p90_seconds": round(max_est, 2),
                    "p95_seconds": round(p95_est, 2),
                    "confidence": confidence,
                }

        # Fallback: use average duration
        durations = [self._duration_seconds(log) or 0 for log in logs]
        if durations:
            avg_duration = sum(durations) / len(durations)
            return {
                "estimated_seconds": round(avg_duration, 2),
                "min_seconds": round(min(durations), 2),
                "max_seconds": round(max(durations), 2),
                "p90_seconds": round(
                    self._percentile(durations, 90) or max(durations), 2
                ),
                "p95_seconds": round(
                    self._percentile(durations, 95) or max(durations), 2
                ),
                "confidence": "medium" if len(durations) >= 5 else "low",
            }

        return {
            "estimated_seconds": None,
            "min_seconds": None,
            "max_seconds": None,
            "confidence": "none",
        }

    def estimate_pipeline_time(
        self,
        modules: List[str],
        transcript_segments: Optional[int] = None,
        transcript_words: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Estimate full pipeline execution time by summing individual module estimates.

        Args:
            modules: List of module names to run
            transcript_segments: Number of segments in transcript (optional)
            transcript_words: Number of words in transcript (optional)

        Returns:
            Dictionary with estimated_seconds, breakdown, confidence
        """
        breakdown = {}
        total_estimated = 0.0
        total_min = 0.0
        total_max = 0.0
        total_p90 = 0.0
        total_p95 = 0.0
        confidences = []

        for module in modules:
            estimate = self.estimate_analysis_time(
                module_name=module,
                transcript_segments=transcript_segments,
                transcript_words=transcript_words,
            )

            breakdown[module] = estimate
            if estimate.get("estimated_seconds") is not None:
                total_estimated += estimate["estimated_seconds"]
                if estimate.get("min_seconds") is not None:
                    total_min += estimate["min_seconds"]
                if estimate.get("max_seconds") is not None:
                    total_max += estimate["max_seconds"]
                if estimate.get("p90_seconds") is not None:
                    total_p90 += estimate["p90_seconds"]
                if estimate.get("p95_seconds") is not None:
                    total_p95 += estimate["p95_seconds"]

            confidences.append(estimate.get("confidence", "none"))

        # Overall confidence is the minimum of all module confidences
        if "high" in confidences and all(c in ("high", "medium") for c in confidences):
            overall_confidence = "high"
        elif "medium" in confidences:
            overall_confidence = "medium"
        elif any(c != "none" for c in confidences):
            overall_confidence = "low"
        else:
            overall_confidence = "none"

        return {
            "estimated_seconds": (
                round(total_estimated, 2) if total_estimated > 0 else None
            ),
            "min_seconds": round(total_min, 2) if total_min > 0 else None,
            "max_seconds": round(total_max, 2) if total_max > 0 else None,
            "p90_seconds": round(total_p90, 2) if total_p90 > 0 else None,
            "p95_seconds": round(total_p95, 2) if total_p95 > 0 else None,
            "breakdown": breakdown,
            "confidence": overall_confidence,
        }


def format_time_estimate(estimate: Dict[str, Any]) -> str:
    """
    Format a time estimate dictionary into a user-friendly string.

    Args:
        estimate: Estimate dictionary from estimator methods

    Returns:
        Formatted string like "2-4 minutes" or "~3 minutes"
    """
    if estimate.get("estimated_seconds") is None:
        return "Unable to estimate (no historical data)"

    est_sec = estimate["estimated_seconds"]
    min_sec = estimate.get("min_seconds", est_sec)
    max_sec = estimate.get("max_seconds", est_sec)

    # Convert to minutes for display
    est_min = est_sec / 60.0
    min_min = min_sec / 60.0
    max_min = max_sec / 60.0

    if est_min < 1:
        # Show in seconds
        if min_sec and max_sec and abs(max_sec - min_sec) > est_sec * 0.2:
            return f"{int(min_sec)}-{int(max_sec)} seconds"
        else:
            return f"~{int(est_sec)} seconds"
    else:
        # Show in minutes
        if min_min and max_min and abs(max_min - min_min) > est_min * 0.2:
            return f"{int(min_min)}-{int(max_min)} minutes"
        else:
            return f"~{int(est_min)} minutes"
