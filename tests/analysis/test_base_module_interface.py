"""
Tests for analysis module base interface and run_from_context contract.

Ensures all analysis modules satisfy the AnalysisModule contract used by
the pipeline (docs/ARCHITECTURE.md).
"""

import pytest

from transcriptx.core.analysis.stats import StatsAnalysis


class TestAnalysisModuleBaseInterface:
    """AnalysisModule base class contract."""

    def test_validate_input_accepts_valid_segments(self):
        segments = [
            {"start": 0.0, "end": 1.0, "text": "Hello", "speaker": "A"},
        ]
        analyzer = StatsAnalysis()
        assert analyzer.validate_input(segments) is True

    def test_validate_input_rejects_empty_segments(self):
        analyzer = StatsAnalysis()
        assert analyzer.validate_input([]) is False

    def test_get_module_info_returns_dict(self):
        analyzer = StatsAnalysis()
        info = analyzer.get_module_info()
        assert isinstance(info, dict)
        assert "name" in info
        assert info["name"] == "stats"
        assert "dependencies" in info
        assert isinstance(info["dependencies"], list)

    def test_get_dependencies_default_empty_for_stats(self):
        analyzer = StatsAnalysis()
        deps = analyzer.get_dependencies()
        assert isinstance(deps, list)
        assert deps == []

    def test_config_must_be_dict_or_none(self):
        with pytest.raises(TypeError, match="config must be None or a dict"):
            StatsAnalysis(config="not a dict")

    def test_config_none_uses_empty_dict(self):
        analyzer = StatsAnalysis()
        assert analyzer.config == {}

    def test_analyze_returns_dict(self):
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Hello world.", "speaker": "Alice"},
            {"start": 2.0, "end": 4.0, "text": "Hi there.", "speaker": "Bob"},
        ]
        analyzer = StatsAnalysis()
        result = analyzer.analyze(segments)
        assert isinstance(result, dict)
        assert "segment_count" in result or "word_count" in result or len(result) >= 1


class TestRunFromContextContract:
    """run_from_context uses context and stores result."""

    def test_run_from_context_returns_dict(self, tmp_path, monkeypatch):
        fixture_path = (
            __import__("pathlib").Path(__file__).resolve().parents[2]
            / "tests"
            / "fixtures"
            / "mini_transcriptx.json"
        )
        if not fixture_path.exists():
            pytest.skip("mini_transcriptx.json not found")
        monkeypatch.setenv("TRANSCRIPTX_DB_ENABLED", "0")
        from transcriptx.core.pipeline.pipeline_context import PipelineContext

        ctx = PipelineContext(
            str(fixture_path),
            output_dir=str(tmp_path),
        )
        try:
            analyzer = StatsAnalysis()
            result = analyzer.run_from_context(ctx)
            assert isinstance(result, dict)
            # Context should have stored the result
            stored = ctx.get_analysis_result("stats")
            assert stored is not None
        finally:
            ctx.close()
