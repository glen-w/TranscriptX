"""
Tests for analysis common utilities (create_module_output_structure, save_analysis_data, validate_segments).
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.analysis.common import (
    create_module_output_structure,
    save_analysis_data,
    validate_segments,
    get_speaker_text_by_speaker,
    get_module_config,
    create_analysis_summary,
    load_transcript_data,
    save_analysis_summary,
    log_analysis_start,
    log_analysis_complete,
    log_analysis_error,
    ensure_directory_exists,
    get_file_size_mb,
    clean_text_for_analysis,
)


class TestCreateModuleOutputStructure:
    """Tests for create_module_output_structure."""

    def test_returns_dict_from_ensure_output_dirs(self, tmp_path):
        transcript_path = str(tmp_path / "demo" / "transcript.json")
        (tmp_path / "demo").mkdir(parents=True, exist_ok=True)
        with patch(
            "transcriptx.core.analysis.common.ensure_output_dirs"
        ) as mock_ensure:
            mock_ensure.return_value = {
                "data_dir": "/out/data",
                "charts_dir": "/out/charts",
            }
            result = create_module_output_structure(transcript_path, "stats")
            mock_ensure.assert_called_once_with(transcript_path, "stats")
            assert result == {"data_dir": "/out/data", "charts_dir": "/out/charts"}


class TestSaveAnalysisData:
    """Tests for save_analysis_data."""

    def test_save_json_creates_file(self, tmp_path):
        output_structure = {
            "data_dir": str(tmp_path),
        }
        data = {"key": "value"}
        path = save_analysis_data(
            data, output_structure, "demo", "result", format_type="json"
        )
        assert path == os.path.join(tmp_path, "demo_result.json")
        assert Path(path).exists()

    def test_save_csv_list_creates_file(self, tmp_path):
        output_structure = {"data_dir": str(tmp_path)}
        data = [["a", "b"], [1, 2]]
        with patch("transcriptx.io.save_csv") as mock_save:
            path = save_analysis_data(
                data, output_structure, "demo", "rows", format_type="csv"
            )
            assert mock_save.called
            assert path.endswith("demo_rows.csv")

    def test_save_txt_dict_creates_file(self, tmp_path):
        output_structure = {"data_dir": str(tmp_path)}
        data = {"a": 1, "b": 2}
        path = save_analysis_data(
            data, output_structure, "demo", "out", format_type="txt"
        )
        assert Path(path).exists()
        assert "a: 1" in Path(path).read_text()

    def test_save_txt_non_dict_uses_str(self, tmp_path):
        output_structure = {"data_dir": str(tmp_path)}
        path = save_analysis_data(
            "plain text", output_structure, "demo", "out", format_type="txt"
        )
        assert Path(path).exists()
        assert Path(path).read_text() == "plain text"

    def test_save_csv_dict_creates_key_value_rows(self, tmp_path):
        output_structure = {"data_dir": str(tmp_path)}
        data = {"k1": "v1", "k2": "v2"}
        with patch("transcriptx.io.save_csv") as mock_save:
            save_analysis_data(
                data, output_structure, "demo", "data", format_type="csv"
            )
            mock_save.assert_called_once()
            args = mock_save.call_args[0]
            assert args[0] == [["k1", "v1"], ["k2", "v2"]]
            assert args[1].endswith("demo_data.csv")

    def test_save_csv_non_list_non_dict_uses_single_row(self, tmp_path):
        output_structure = {"data_dir": str(tmp_path)}
        with patch("transcriptx.io.save_csv") as mock_save:
            path = save_analysis_data(
                42, output_structure, "demo", "x", format_type="csv"
            )
            mock_save.assert_called_once()
            assert mock_save.call_args[0][0] == [[42]]
            assert path.endswith("demo_x.csv")

    def test_unsupported_format_raises(self, tmp_path):
        output_structure = {"data_dir": str(tmp_path)}
        with pytest.raises(ValueError, match="Unsupported format type"):
            save_analysis_data({}, output_structure, "demo", "x", format_type="xml")


class TestValidateSegments:
    """Tests for validate_segments."""

    def test_empty_returns_false(self):
        assert validate_segments([]) is False

    def test_valid_segments_returns_true(self):
        segments = [
            {"speaker": "S1", "text": "Hello"},
            {"speaker": "S2", "text": "Hi"},
        ]
        assert validate_segments(segments) is True

    def test_missing_speaker_returns_false(self):
        segments = [{"text": "Hello"}]
        assert validate_segments(segments) is False

    def test_missing_text_returns_false(self):
        segments = [{"speaker": "S1"}]
        assert validate_segments(segments) is False

    def test_non_dict_segment_returns_false(self):
        segments = [{"speaker": "S1", "text": "Hi"}, "not a dict"]
        assert validate_segments(segments) is False


class TestGetModuleConfig:
    """Tests for get_module_config."""

    def test_returns_default_empty_when_no_module_attr(self):
        with patch("transcriptx.core.analysis.common.get_config") as mock_config:
            mock_config.return_value = type("C", (), {})()
            result = get_module_config("nonexistent")
            assert result == {}

    def test_returns_module_attr_when_present(self):
        with patch("transcriptx.core.analysis.common.get_config") as mock_config:
            mod = {"key": "value"}
            mock_config.return_value = type("C", (), {"stats": mod})()
            result = get_module_config("stats")
            assert result is mod


class TestCreateAnalysisSummary:
    """Tests for create_analysis_summary."""

    def test_success_summary(self):
        output_structure = {"module_dir": "/out/stats"}
        result = create_analysis_summary(
            "stats", "demo", output_structure, {"count": 10}
        )
        assert result["module"] == "stats"
        assert result["transcript"] == "demo"
        assert result["status"] == "success"
        assert result["results"] == {"count": 10}

    def test_partial_summary_with_errors(self):
        output_structure = {"module_dir": "/out/stats"}
        result = create_analysis_summary(
            "stats", "demo", output_structure, {}, errors=["err1"]
        )
        assert result["status"] == "partial"
        assert result["errors"] == ["err1"]


class TestGetSpeakerTextBySpeaker:
    """Tests for get_speaker_text_by_speaker."""

    def test_groups_text_by_speaker(self):
        segments = [
            {"speaker": "Alice", "text": "Hello"},
            {"speaker": "Bob", "text": "Hi"},
            {"speaker": "Alice", "text": "Bye"},
        ]
        with patch(
            "transcriptx.core.utils.speaker_extraction.group_segments_by_speaker"
        ) as mock_group:
            mock_group.return_value = {
                "Alice": [segments[0], segments[2]],
                "Bob": [segments[1]],
            }
            result = get_speaker_text_by_speaker(segments)
            mock_group.assert_called_once_with(segments)
            assert result["Alice"] == ["Hello", "Bye"]
            assert result["Bob"] == ["Hi"]


class TestLoadTranscriptData:
    """Tests for load_transcript_data."""

    def test_delegates_to_service_and_returns_tuple(self):
        with patch(
            "transcriptx.io.transcript_service.get_transcript_service"
        ) as mock_get_svc:
            mock_svc = mock_get_svc.return_value
            mock_svc.load_transcript_data.return_value = (
                [{"speaker": "S1", "text": "Hi"}],
                "base",
                "/out/dir",
                {},
            )
            segments, base_name, transcript_dir, speaker_map = load_transcript_data(
                "/path/to/transcript.json"
            )
            mock_svc.load_transcript_data.assert_called_once_with(
                "/path/to/transcript.json",
                skip_speaker_mapping=False,
                batch_mode=False,
            )
            assert segments == [{"speaker": "S1", "text": "Hi"}]
            assert base_name == "base"
            assert transcript_dir == "/out/dir"
            assert speaker_map == {}

    def test_emits_deprecation_warning_when_speaker_map_non_empty(self):
        with patch(
            "transcriptx.io.transcript_service.get_transcript_service"
        ) as mock_get_svc:
            mock_get_svc.return_value.load_transcript_data.return_value = (
                [],
                "base",
                "/out",
                {"S1": "Alice"},
            )
            with pytest.warns(DeprecationWarning, match="speaker_map.*deprecated"):
                load_transcript_data("/path/to/file.json")


class TestSaveAnalysisSummary:
    """Tests for save_analysis_summary."""

    def test_writes_summary_json_and_returns_path(self, tmp_path):
        output_structure = {"data_dir": str(tmp_path)}
        summary = {
            "module": "stats",
            "transcript": "demo",
            "results": {"n": 5},
        }
        path = save_analysis_summary(summary, output_structure, "demo")
        assert path == os.path.join(tmp_path, "demo_stats_summary.json")
        assert Path(path).exists()
        import json

        loaded = json.loads(Path(path).read_text())
        assert loaded["module"] == "stats"


class TestLogAnalysisHelpers:
    """Tests for log_analysis_start, log_analysis_complete, log_analysis_error."""

    def test_log_analysis_start(self):
        with patch("transcriptx.core.analysis.common.logger") as mock_log:
            log_analysis_start("stats", "/path/to/transcript.json")
            mock_log.info.assert_called_once()
            call_arg = mock_log.info.call_args[0][0]
            assert "Starting" in call_arg and "stats" in call_arg

    def test_log_analysis_complete(self):
        with patch("transcriptx.core.analysis.common.logger") as mock_log:
            log_analysis_complete("sentiment", "/p/x.json")
            mock_log.info.assert_called_once()
            assert "Completed" in mock_log.info.call_args[0][0]

    def test_log_analysis_error(self):
        with patch("transcriptx.core.analysis.common.logger") as mock_log:
            log_analysis_error("ner", "/p/x.json", "something failed")
            mock_log.error.assert_called_once()
            assert "Error" in mock_log.error.call_args[0][0]
            assert "something failed" in mock_log.error.call_args[0][0]


class TestEnsureDirectoryExists:
    """Tests for ensure_directory_exists."""

    def test_creates_directory(self, tmp_path):
        dir_path = str(tmp_path / "new_subdir")
        ensure_directory_exists(dir_path)
        assert Path(dir_path).is_dir()

    def test_idempotent_when_exists(self, tmp_path):
        (tmp_path / "existing").mkdir()
        ensure_directory_exists(str(tmp_path / "existing"))
        assert (tmp_path / "existing").is_dir()


class TestGetFileSizeMb:
    """Tests for get_file_size_mb."""

    def test_nonexistent_returns_zero(self):
        assert get_file_size_mb("/nonexistent/path/file.txt") == 0.0

    def test_existing_file_returns_size_mb(self, tmp_path):
        f = tmp_path / "f.bin"
        f.write_bytes(b"x" * (1024 * 1024))  # 1 MB
        assert get_file_size_mb(str(f)) == 1.0


class TestCleanTextForAnalysis:
    """Tests for clean_text_for_analysis."""

    def test_empty_returns_empty(self):
        assert clean_text_for_analysis("") == ""

    def test_normalizes_whitespace(self):
        assert clean_text_for_analysis("  a   b  c  ") == "a b c"

    def test_removes_artifacts(self):
        text = "Hello [inaudible] world [unclear] end [crosstalk]."
        assert "[inaudible]" not in clean_text_for_analysis(text)
        assert "[unclear]" not in clean_text_for_analysis(text)
        assert "[crosstalk]" not in clean_text_for_analysis(text)
        assert clean_text_for_analysis(text) == "Hello  world  end ."
