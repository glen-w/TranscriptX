"""
Tests for sentiment analysis module.

This module tests sentiment analysis output contracts (offline-safe).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.sentiment import SentimentAnalysis  # type: ignore[import-untyped]


class TestSentimentAnalysisModule:
    """Tests for SentimentAnalysis."""

    @pytest.fixture
    def sentiment_module(self) -> SentimentAnalysis:
        """Fixture for SentimentAnalysis instance."""
        return SentimentAnalysis()

    @pytest.fixture
    def sample_segments(self) -> list[dict[str, Any]]:
        """Fixture for sample transcript segments with segment-based speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I love this product!",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "This is terrible.",
                "start": 2.0,
                "end": 4.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "It's okay, I guess.",
                "start": 4.0,
                "end": 6.0,
            },
        ]

    @pytest.fixture
    def sample_speaker_map(self) -> dict[str, str]:
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}

    def test_sentiment_analysis_basic(
        self,
        sentiment_module: SentimentAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test basic sentiment analysis."""
        result = sentiment_module.analyze(sample_segments)

        assert "segments_with_sentiment" in result
        segments = result["segments_with_sentiment"]
        assert len(segments) == len(sample_segments)
        for seg in segments:
            sentiment = seg.get("sentiment")
            assert isinstance(sentiment, dict)
            assert {"compound", "pos", "neu", "neg"}.issubset(set(sentiment.keys()))
            # normalized keys are a stable contract across backends
            assert "sentiment_compound_norm" in seg
            assert -1.0 <= float(seg["sentiment_compound_norm"]) <= 1.0

    def test_sentiment_analysis_positive_text(
        self, sentiment_module: SentimentAnalysis, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test sentiment analysis on positive text."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "This is amazing! I love it!",
                "start": 0.0,
                "end": 2.0,
            }
        ]

        result = sentiment_module.analyze(segments)

        # Should detect positive sentiment
        sentiment = result["segments_with_sentiment"][0]["sentiment"]
        assert float(sentiment.get("compound", 0.0)) > 0

    def test_sentiment_analysis_negative_text(
        self, sentiment_module: SentimentAnalysis, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test sentiment analysis on negative text."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "This is terrible. I hate it.",
                "start": 0.0,
                "end": 2.0,
            }
        ]

        result = sentiment_module.analyze(segments)

        # Should detect negative sentiment
        sentiment = result["segments_with_sentiment"][0]["sentiment"]
        assert float(sentiment.get("compound", 0.0)) < 0

    def test_sentiment_analysis_neutral_text(
        self, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test sentiment analysis on neutral text."""
        mock_cfg = MagicMock()
        mock_cfg.analysis.sentiment_backend = "vader"
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "The weather is fine today.",
                "start": 0.0,
                "end": 2.0,
            }
        ]

        with patch(
            "transcriptx.core.utils.config.get_config",
            return_value=mock_cfg,
        ):
            sentiment_module = SentimentAnalysis()
            result = sentiment_module.analyze(segments)

        # Should detect neutral sentiment
        sentiment = result["segments_with_sentiment"][0]["sentiment"]
        assert abs(float(sentiment.get("compound", 0.0))) < 0.4

    def test_sentiment_analysis_speaker_aggregation(
        self,
        sentiment_module: SentimentAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test sentiment aggregation by speaker."""
        result = sentiment_module.analyze(sample_segments)

        # Should include speaker-level aggregation
        assert "speaker_analysis" in result
        assert "speaker_stats" in result

    def test_sentiment_analysis_empty_segments(
        self, sentiment_module: SentimentAnalysis, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test sentiment analysis with empty segments."""
        segments: list[dict[str, Any]] = []

        result = sentiment_module.analyze(segments)

        assert "segments_with_sentiment" in result
        assert result["segments_with_sentiment"] == []

    def test_sentiment_smoke_charts(
        self,
        sentiment_module: SentimentAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
        temp_transcript_file: Any,
    ) -> None:
        """Smoke test for chart + data writes (contract only)."""
        results = sentiment_module.analyze(sample_segments)

        output_service = MagicMock()
        output_service.base_name = "test_transcript"
        output_service.transcript_path = str(temp_transcript_file)
        output_service.save_data = MagicMock()
        output_service.save_chart = MagicMock()
        output_service.save_summary = MagicMock()

        with (
            patch(
                "transcriptx.core.analysis.sentiment.write_enriched_transcript",
                return_value=str(temp_transcript_file),
            ),
        ):
            sentiment_module._save_results(results, output_service)

        assert output_service.save_data.called
        assert output_service.save_chart.called or output_service.save_summary.called


class TestSentimentTransformersLoad:
    """Regression: torch<2.6 cannot torch.load Hub bins; load local safetensors."""

    def test_load_uses_local_snapshot_path_with_safetensors(self, tmp_path) -> None:
        """Hub metadata ignores converted files — must pass local path, not repo id."""
        from contextlib import nullcontext
        from pathlib import Path

        from transcriptx.core.analysis.sentiment import _load_sentiment_transformers

        local_root = tmp_path / "snap"
        local_root.mkdir()
        pipe = MagicMock(name="pipe")
        transformers = MagicMock()
        transformers.pipeline.return_value = pipe

        with (
            patch(
                "transcriptx.core.analysis.hf_safetensors.ensure_local_safetensors",
                return_value=Path(local_root),
            ),
            patch(
                "transcriptx.core.utils.lazy_imports.get_transformers",
                return_value=transformers,
            ),
            patch(
                "transcriptx.core.analysis.sentiment.suppress_stdout_stderr",
                return_value=nullcontext(),
            ),
            patch(
                "transcriptx.core.analysis.sentiment.spinner",
                return_value=nullcontext(),
            ),
        ):
            got = _load_sentiment_transformers(
                "cardiffnlp/twitter-roberta-base-sentiment-latest"
            )

        assert got is pipe
        transformers.pipeline.assert_called()
        kwargs = transformers.pipeline.call_args.kwargs
        assert kwargs["model"] == str(local_root)
        assert kwargs.get("model_kwargs", {}).get("use_safetensors") is True
        # Must not fall back to Hub repo id (cache won't see converted weights).
        assert kwargs["model"] != "cardiffnlp/twitter-roberta-base-sentiment-latest"

    def test_load_falls_back_to_repo_id_when_no_local_safetensors(self) -> None:
        from contextlib import nullcontext

        from transcriptx.core.analysis.sentiment import _load_sentiment_transformers

        pipe = MagicMock(name="pipe")
        transformers = MagicMock()
        transformers.pipeline.return_value = pipe

        with (
            patch(
                "transcriptx.core.analysis.hf_safetensors.ensure_local_safetensors",
                return_value=None,
            ),
            patch(
                "transcriptx.core.utils.lazy_imports.get_transformers",
                return_value=transformers,
            ),
            patch(
                "transcriptx.core.analysis.sentiment.suppress_stdout_stderr",
                return_value=nullcontext(),
            ),
            patch(
                "transcriptx.core.analysis.sentiment.spinner",
                return_value=nullcontext(),
            ),
        ):
            got = _load_sentiment_transformers("org/sentiment-model")

        assert got is pipe
        assert transformers.pipeline.call_args.kwargs["model"] == "org/sentiment-model"

    def test_load_returns_none_when_pipeline_raises(self) -> None:
        from contextlib import nullcontext

        from transcriptx.core.analysis.sentiment import _load_sentiment_transformers

        transformers = MagicMock()
        transformers.pipeline.side_effect = ValueError(
            "Due to a serious vulnerability issue in torch.load"
        )

        with (
            patch(
                "transcriptx.core.analysis.hf_safetensors.ensure_local_safetensors",
                return_value=None,
            ),
            patch(
                "transcriptx.core.utils.lazy_imports.get_transformers",
                return_value=transformers,
            ),
            patch(
                "transcriptx.core.analysis.sentiment.suppress_stdout_stderr",
                return_value=nullcontext(),
            ),
            patch(
                "transcriptx.core.analysis.sentiment.spinner",
                return_value=nullcontext(),
            ),
            patch("transcriptx.core.analysis.sentiment.notify_user"),
        ):
            assert _load_sentiment_transformers("org/broken") is None
