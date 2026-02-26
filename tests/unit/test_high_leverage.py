"""
High-leverage unit tests for core APIs.

These tests target the most critical paths: config lifecycle, validation,
module registry, and transcript loading. They are fast, deterministic,
and require no external services.
"""

from __future__ import annotations

import json

import pytest

from transcriptx.core.utils.config import (
    get_config,
    set_config,
    load_config,
    TranscriptXConfig,
)
from transcriptx.core.utils.validation import (
    validate_transcript_file,
    validate_segment,
)
from transcriptx.core.pipeline.module_registry import (
    get_available_modules,
    get_module_info,
    get_module_function,
    get_dependencies,
)
from transcriptx.io.transcript_loader import load_segments


class TestConfigLifecycle:
    """Config get/set/load roundtrip and identity."""

    def test_get_config_returns_transcript_x_config(self):
        """get_config() returns an instance of TranscriptXConfig."""
        config = get_config()
        assert isinstance(config, TranscriptXConfig)

    def test_get_config_has_required_sections(self):
        """Config has analysis, transcription, output, logging."""
        config = get_config()
        assert hasattr(config, "analysis")
        assert hasattr(config, "transcription")
        assert hasattr(config, "output")
        assert hasattr(config, "logging")

    def test_set_config_updates_global(self):
        """set_config() updates the global config returned by get_config()."""
        original = get_config()
        fresh = TranscriptXConfig()
        fresh.analysis.sentiment_window_size = 999
        set_config(fresh)
        try:
            current = get_config()
            assert current is fresh
            assert current.analysis.sentiment_window_size == 999
        finally:
            set_config(original)

    def test_load_config_from_file(self, tmp_path):
        """load_config(path) loads JSON and sets global config."""
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "analysis": {"sentiment_window_size": 42},
                    "transcription": {},
                    "output": {},
                    "logging": {},
                }
            )
        )
        original = get_config()
        try:
            loaded = load_config(str(config_path))
            assert loaded.analysis.sentiment_window_size == 42
            assert get_config() is loaded
        finally:
            set_config(original)


class TestValidationHighLeverage:
    """Validation edge cases that protect pipeline input."""

    def test_validate_transcript_file_empty_path_raises(self):
        """Empty path raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_transcript_file("")

    def test_validate_segment_missing_text_raises(self):
        """Segment missing 'text' raises ValueError."""
        with pytest.raises(ValueError, match="required field"):
            validate_segment({"speaker": "S1"}, 0)

    def test_validate_segment_missing_speaker_raises(self):
        """Segment missing 'speaker' raises ValueError."""
        with pytest.raises(ValueError, match="required field"):
            validate_segment({"text": "hello"}, 0)

    def test_validate_segment_not_dict_raises(self):
        """Segment that is not a dict raises ValueError."""
        with pytest.raises(ValueError, match="must be a dictionary"):
            validate_segment("not a dict", 0)


class TestModuleRegistryHighLeverage:
    """Module registry: availability, info, and callable entrypoints."""

    def test_get_available_modules_non_empty(self):
        """At least one module is available."""
        modules = get_available_modules()
        assert isinstance(modules, list)
        assert len(modules) > 0

    def test_stats_module_available_and_callable(self):
        """'stats' module exists and get_module_function returns a callable."""
        modules = get_available_modules()
        assert "stats" in modules
        func = get_module_function("stats")
        assert func is not None
        assert callable(func)

    def test_get_module_info_returns_info_or_none(self):
        """get_module_info('stats') returns ModuleInfo; nonexistent returns None."""
        info = get_module_info("stats")
        assert info is not None
        assert info.name == "stats"
        assert get_module_info("nonexistent_xyz") is None

    def test_get_dependencies_returns_list(self):
        """get_dependencies returns a list for any module id."""
        deps = get_dependencies("stats")
        assert isinstance(deps, list)


class TestTranscriptLoaderHighLeverage:
    """load_segments: shapes that feed the pipeline."""

    def test_load_segments_empty_list(self, tmp_path):
        """JSON with empty segments list returns []."""
        path = tmp_path / "empty.json"
        path.write_text(json.dumps({"segments": []}))
        assert load_segments(str(path)) == []

    def test_load_segments_direct_list_root(self, tmp_path):
        """JSON that is a direct list of segments loads correctly."""
        path = tmp_path / "list.json"
        segments = [
            {"speaker": "A", "text": "Hi", "start": 0.0, "end": 1.0},
            {"speaker": "B", "text": "Bye", "start": 1.0, "end": 2.0},
        ]
        path.write_text(json.dumps(segments))
        assert load_segments(str(path)) == segments
