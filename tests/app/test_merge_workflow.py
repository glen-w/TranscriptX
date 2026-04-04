"""
Unit tests for app.workflows.merge.run_merge.

All external I/O is mocked so no ffmpeg, audio files, or network is needed.
Tests cover every early-exit validation branch and the happy-path merge dispatch.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.app.models.requests import MergeRequest
from transcriptx.app.models.results import MergeResult
from transcriptx.app.progress import NullProgress
from transcriptx.app.workflows.merge import run_merge

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FFMPEG_OK = (True, None)
_FFMPEG_FAIL = (False, "ffmpeg not found")


def _make_files(tmp_path: Path, count: int, suffix: str = ".wav") -> list[Path]:
    """Create *count* real (empty) temp files with the given suffix."""
    files = []
    for i in range(count):
        p = tmp_path / f"file_{i}{suffix}"
        p.write_bytes(b"")
        files.append(p)
    return files


# ---------------------------------------------------------------------------
# Validation: ffmpeg check
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMergeValidation:
    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_FAIL,
    )
    def test_ffmpeg_unavailable_returns_failure(self, _mock_ffmpeg, tmp_path):
        files = _make_files(tmp_path, 2)
        req = MergeRequest(file_paths=files, output_dir=tmp_path)
        result = run_merge(req)
        assert not result.success
        assert any("ffmpeg" in e.lower() for e in result.errors)

    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    def test_fewer_than_two_files_returns_failure(self, _mock_ffmpeg, tmp_path):
        files = _make_files(tmp_path, 1)
        req = MergeRequest(file_paths=files, output_dir=tmp_path)
        result = run_merge(req)
        assert not result.success
        assert any("2" in e for e in result.errors)

    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    def test_duplicate_files_returns_failure(self, _mock_ffmpeg, tmp_path):
        files = _make_files(tmp_path, 1)
        req = MergeRequest(file_paths=[files[0], files[0]], output_dir=tmp_path)
        result = run_merge(req)
        assert not result.success
        assert any("duplicate" in e.lower() for e in result.errors)

    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    def test_missing_files_returns_failure(self, _mock_ffmpeg, tmp_path):
        ghost = tmp_path / "ghost.wav"  # does not exist
        real = tmp_path / "real.wav"
        real.write_bytes(b"")
        req = MergeRequest(file_paths=[real, ghost], output_dir=tmp_path)
        result = run_merge(req)
        assert not result.success
        assert any("not found" in e.lower() for e in result.errors)

    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    def test_unsupported_extension_returns_failure(self, _mock_ffmpeg, tmp_path):
        files = _make_files(tmp_path, 2, suffix=".txt")
        req = MergeRequest(file_paths=files, output_dir=tmp_path)
        result = run_merge(req)
        assert not result.success
        assert any("unsupported" in e.lower() for e in result.errors)

    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    def test_output_exists_without_overwrite_returns_failure(
        self, _mock_ffmpeg, tmp_path
    ):
        files = _make_files(tmp_path, 2)
        output = tmp_path / "out.mp3"
        output.write_bytes(b"existing")
        req = MergeRequest(
            file_paths=files,
            output_dir=tmp_path,
            output_filename="out.mp3",
            overwrite=False,
        )
        result = run_merge(req)
        assert not result.success
        assert any("already exists" in e.lower() for e in result.errors)

    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    def test_output_same_as_input_returns_failure(self, _mock_ffmpeg, tmp_path):
        # Use .mp3 inputs so the auto-extension logic doesn't change the name,
        # then specify the output to match the first input exactly.
        files = _make_files(tmp_path, 2, suffix=".mp3")
        req = MergeRequest(
            file_paths=files,
            output_dir=tmp_path,
            output_filename=files[0].name,
            overwrite=True,
            backup_wavs=False,
        )
        result = run_merge(req)
        assert not result.success
        assert any("same as one of the input" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# Output filename derivation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMergeOutputFilename:
    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    @patch("transcriptx.app.workflows.merge.merge_audio_files")
    def test_explicit_filename_without_mp3_gets_extension_added(
        self, mock_merge, _mock_ffmpeg, tmp_path
    ):
        files = _make_files(tmp_path, 2)
        mock_merge.return_value = tmp_path / "custom.mp3"
        req = MergeRequest(
            file_paths=files,
            output_dir=tmp_path,
            output_filename="custom",
            backup_wavs=False,
        )
        result = run_merge(req)
        assert result.success
        called_output: Path = mock_merge.call_args[0][1]
        assert called_output.name == "custom.mp3"

    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    @patch("transcriptx.app.workflows.merge.merge_audio_files")
    @patch(
        "transcriptx.app.workflows.merge.extract_date_prefix", return_value="20240101_"
    )
    def test_auto_filename_uses_date_prefix(
        self, _mock_date, mock_merge, _mock_ffmpeg, tmp_path
    ):
        files = _make_files(tmp_path, 2)
        expected_out = tmp_path / "20240101_merged.mp3"
        mock_merge.return_value = expected_out
        req = MergeRequest(file_paths=files, output_dir=tmp_path, backup_wavs=False)
        result = run_merge(req)
        assert result.success
        called_output: Path = mock_merge.call_args[0][1]
        assert called_output.name == "20240101_merged.mp3"

    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    @patch("transcriptx.app.workflows.merge.merge_audio_files")
    @patch("transcriptx.app.workflows.merge.extract_date_prefix", return_value=None)
    def test_auto_filename_fallback_when_no_date_prefix(
        self, _mock_date, mock_merge, _mock_ffmpeg, tmp_path
    ):
        files = _make_files(tmp_path, 2)
        mock_merge.return_value = tmp_path / "merged_fallback.mp3"
        req = MergeRequest(file_paths=files, output_dir=tmp_path, backup_wavs=False)
        result = run_merge(req)
        assert result.success
        called_output: Path = mock_merge.call_args[0][1]
        assert called_output.name.startswith("merged_")
        assert called_output.name.endswith(".mp3")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMergeHappyPath:
    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    @patch("transcriptx.app.workflows.merge.merge_audio_files")
    def test_success_returns_merge_result(self, mock_merge, _mock_ffmpeg, tmp_path):
        files = _make_files(tmp_path, 3)
        expected_out = tmp_path / "result.mp3"
        mock_merge.return_value = expected_out
        req = MergeRequest(
            file_paths=files,
            output_dir=tmp_path,
            output_filename="result.mp3",
            backup_wavs=False,
        )
        result = run_merge(req)
        assert result.success
        assert result.output_path == expected_out
        assert result.files_merged == 3
        assert result.errors == []

    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    @patch("transcriptx.app.workflows.merge.merge_audio_files")
    def test_merge_exception_returns_failed_result(
        self, mock_merge, _mock_ffmpeg, tmp_path
    ):
        files = _make_files(tmp_path, 2)
        mock_merge.side_effect = RuntimeError("codec error")
        req = MergeRequest(
            file_paths=files,
            output_dir=tmp_path,
            output_filename="result.mp3",
            backup_wavs=False,
        )
        result = run_merge(req)
        assert not result.success
        assert any("codec error" in e for e in result.errors)

    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    @patch("transcriptx.app.workflows.merge.merge_audio_files")
    def test_progress_stages_are_called(self, mock_merge, _mock_ffmpeg, tmp_path):
        files = _make_files(tmp_path, 2)
        mock_merge.return_value = tmp_path / "out.mp3"
        progress = MagicMock()
        req = MergeRequest(
            file_paths=files,
            output_dir=tmp_path,
            output_filename="out.mp3",
            backup_wavs=False,
        )
        run_merge(req, progress=progress)
        stage_names = [c.args[0] for c in progress.on_stage_start.call_args_list]
        assert "validating" in stage_names
        assert "backing_up" in stage_names
        assert "merging" in stage_names
        assert "completed" in stage_names

    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    @patch("transcriptx.app.workflows.merge.merge_audio_files")
    def test_null_progress_does_not_raise(self, mock_merge, _mock_ffmpeg, tmp_path):
        files = _make_files(tmp_path, 2)
        mock_merge.return_value = tmp_path / "out.mp3"
        req = MergeRequest(
            file_paths=files,
            output_dir=tmp_path,
            output_filename="out.mp3",
            backup_wavs=False,
        )
        result = run_merge(req, progress=NullProgress())
        assert result.success


# ---------------------------------------------------------------------------
# Backup branch
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMergeBackup:
    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    @patch("transcriptx.app.workflows.merge.merge_audio_files")
    @patch(
        "transcriptx.app.workflows.merge.backup_audio_files_to_storage",
        return_value=[],
    )
    def test_backup_empty_result_adds_warning(
        self, _mock_backup, mock_merge, _mock_ffmpeg, tmp_path
    ):
        files = _make_files(tmp_path, 2)
        mock_merge.return_value = tmp_path / "out.mp3"
        req = MergeRequest(
            file_paths=files,
            output_dir=tmp_path,
            output_filename="out.mp3",
            backup_wavs=True,
        )
        result = run_merge(req)
        assert result.success
        assert any("no output files" in w.lower() for w in result.warnings)

    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    @patch("transcriptx.app.workflows.merge.merge_audio_files")
    @patch(
        "transcriptx.app.workflows.merge.backup_audio_files_to_storage",
        side_effect=OSError("disk full"),
    )
    def test_backup_exception_adds_warning_merge_continues(
        self, _mock_backup, mock_merge, _mock_ffmpeg, tmp_path
    ):
        files = _make_files(tmp_path, 2)
        mock_merge.return_value = tmp_path / "out.mp3"
        req = MergeRequest(
            file_paths=files,
            output_dir=tmp_path,
            output_filename="out.mp3",
            backup_wavs=True,
        )
        result = run_merge(req)
        assert result.success
        assert any("backup" in w.lower() for w in result.warnings)
        mock_merge.assert_called_once()


# ---------------------------------------------------------------------------
# MergeController delegation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMergeController:
    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_FAIL,
    )
    def test_controller_returns_failed_result_on_validation_error(
        self, _mock_ffmpeg, tmp_path
    ):
        from transcriptx.app.controllers.merge_controller import MergeController

        files = _make_files(tmp_path, 2)
        req = MergeRequest(file_paths=files, output_dir=tmp_path)
        ctrl = MergeController()
        result = ctrl.run_merge(req)
        assert isinstance(result, MergeResult)
        assert not result.success

    @patch(
        "transcriptx.app.workflows.merge.check_ffmpeg_available",
        return_value=_FFMPEG_OK,
    )
    @patch("transcriptx.app.workflows.merge.merge_audio_files")
    def test_controller_returns_success_result(
        self, mock_merge, _mock_ffmpeg, tmp_path
    ):
        from transcriptx.app.controllers.merge_controller import MergeController

        files = _make_files(tmp_path, 2)
        mock_merge.return_value = tmp_path / "out.mp3"
        req = MergeRequest(
            file_paths=files,
            output_dir=tmp_path,
            output_filename="out.mp3",
            backup_wavs=False,
        )
        ctrl = MergeController()
        result = ctrl.run_merge(req)
        assert isinstance(result, MergeResult)
        assert result.success

    def test_controller_raises_workflow_execution_error_on_unexpected_exception(
        self, tmp_path
    ):
        from transcriptx.app.controllers.merge_controller import MergeController
        from transcriptx.app.models.errors import WorkflowExecutionError

        ctrl = MergeController()
        with patch(
            "transcriptx.app.controllers.merge_controller.run_merge",
            side_effect=RuntimeError("unexpected"),
        ):
            with pytest.raises(WorkflowExecutionError):
                ctrl.run_merge(MergeRequest(file_paths=[], output_dir=tmp_path))
