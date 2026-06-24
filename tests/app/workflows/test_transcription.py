"""Tests for transcription workflow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.app.models.requests import (
    TranscriptionConversionOptions,
    TranscriptionOptions,
    TranscriptionRequest,
)
from transcriptx.app.models.results import TranscriptionProviderResult
from transcriptx.app.progress import NullProgress
from transcriptx.app.workflows.transcription import run_transcription_workflow


def _provider_result(
    json_path: Path, *, success: bool = True
) -> TranscriptionProviderResult:
    return TranscriptionProviderResult(
        success=success,
        json_path=json_path if success else None,
        output_dir=json_path.parent,
        returncode=0 if success else 1,
        stdout_tail=(),
        stderr_tail=("err",) if not success else (),
        duration_seconds=1.0,
        error=None if success else "failed",
    )


@pytest.mark.unit
class TestTranscriptionWorkflow:
    @patch("transcriptx.app.workflows.transcription.run_managed_import_workflow")
    @patch("transcriptx.app.workflows.transcription.get_provider")
    @patch("transcriptx.app.workflows.transcription.export_mp3_for_transcription")
    def test_single_wav_success_import_off(
        self, mock_convert, mock_get_provider, mock_import, tmp_path: Path
    ):
        wav = tmp_path / "meeting.wav"
        wav.write_bytes(b"wav")
        staged = tmp_path / "staging" / "meeting.mp3"
        staged.parent.mkdir(parents=True)
        mock_convert.return_value = staged

        json_out = tmp_path / "json" / "meeting.json"
        json_out.parent.mkdir(parents=True)
        json_out.write_text("{}", encoding="utf-8")

        provider = MagicMock()
        provider.provider_id = "whispermlx"
        provider.transcribe.return_value = _provider_result(json_out)
        mock_get_provider.return_value = provider

        request = TranscriptionRequest(
            input_paths=[wav],
            transcription_options=TranscriptionOptions(
                provider_id="whispermlx",
                model="large-v3",
                language="en",
                diarize=False,
            ),
            conversion_options=TranscriptionConversionOptions(),
            import_into_library=False,
        )
        result = run_transcription_workflow(request, NullProgress())
        assert result.succeeded_count == 1
        mock_import.assert_not_called()

    @patch("transcriptx.app.workflows.transcription.run_managed_import_workflow")
    @patch("transcriptx.app.workflows.transcription.get_provider")
    @patch("transcriptx.app.workflows.transcription.export_mp3_for_transcription")
    def test_single_wav_success_import_on(
        self, mock_convert, mock_get_provider, mock_import, tmp_path: Path
    ):
        wav = tmp_path / "meeting.wav"
        wav.write_bytes(b"wav")
        staged = tmp_path / "staging" / "meeting.mp3"
        mock_convert.return_value = staged

        json_out = tmp_path / "json" / "meeting.json"
        json_out.parent.mkdir(parents=True)
        json_out.write_text("{}", encoding="utf-8")

        imported = tmp_path / "library" / "meeting.json"
        mock_import.return_value = MagicMock(json_path=imported)

        provider = MagicMock()
        provider.provider_id = "whispermlx"
        provider.transcribe.return_value = _provider_result(json_out)
        mock_get_provider.return_value = provider

        request = TranscriptionRequest(
            input_paths=[wav],
            transcription_options=TranscriptionOptions(
                provider_id="whispermlx",
                model="large-v3",
                language="en",
                diarize=False,
            ),
            conversion_options=TranscriptionConversionOptions(),
            import_into_library=True,
        )
        result = run_transcription_workflow(request, NullProgress())
        assert result.file_results[0].import_success is True
        mock_import.assert_called_once()

    @patch("transcriptx.app.workflows.transcription.get_provider")
    @patch("transcriptx.app.workflows.transcription.export_mp3_for_transcription")
    def test_mp3_skip_does_not_delete_original(
        self, mock_convert, mock_get_provider, tmp_path: Path
    ):
        mp3 = tmp_path / "clip.mp3"
        mp3.write_bytes(b"mp3")
        mock_convert.return_value = mp3  # skip conversion

        json_out = tmp_path / "json" / "clip.json"
        json_out.parent.mkdir(parents=True)
        json_out.write_text("{}", encoding="utf-8")

        provider = MagicMock()
        provider.provider_id = "whispermlx"
        provider.transcribe.return_value = _provider_result(json_out)
        mock_get_provider.return_value = provider

        request = TranscriptionRequest(
            input_paths=[mp3],
            transcription_options=TranscriptionOptions(
                provider_id="whispermlx",
                model="large-v3",
                language="en",
                diarize=False,
            ),
            conversion_options=TranscriptionConversionOptions(),
            import_into_library=False,
            keep_intermediates=False,
        )
        result = run_transcription_workflow(request, NullProgress())
        assert mp3.exists()
        assert result.file_results[0].created_staged_file is False

    def test_unsupported_extension_fails_per_file(self, tmp_path: Path):
        bad = tmp_path / "notes.txt"
        bad.write_text("x", encoding="utf-8")
        request = TranscriptionRequest(
            input_paths=[bad],
            transcription_options=TranscriptionOptions(
                provider_id="whispermlx",
                model="large-v3",
                language="en",
                diarize=False,
            ),
            conversion_options=TranscriptionConversionOptions(),
        )
        result = run_transcription_workflow(request, NullProgress())
        assert result.failed_count == 1

    @patch("transcriptx.app.workflows.transcription.run_managed_import_workflow")
    @patch("transcriptx.app.workflows.transcription.get_provider")
    @patch("transcriptx.app.workflows.transcription.export_mp3_for_transcription")
    def test_batch_continues_after_failure(
        self, mock_convert, mock_get_provider, mock_import, tmp_path: Path
    ):
        good = tmp_path / "a.wav"
        bad = tmp_path / "b.wav"
        good.write_bytes(b"a")
        bad.write_bytes(b"b")
        staged = tmp_path / "a.mp3"
        mock_convert.side_effect = [staged, RuntimeError("convert failed")]

        json_out = tmp_path / "json" / "a.json"
        json_out.parent.mkdir(parents=True)
        json_out.write_text("{}", encoding="utf-8")

        provider = MagicMock()
        provider.provider_id = "whispermlx"
        provider.transcribe.return_value = _provider_result(json_out)
        mock_get_provider.return_value = provider

        request = TranscriptionRequest(
            input_paths=[good, bad],
            transcription_options=TranscriptionOptions(
                provider_id="whispermlx",
                model="large-v3",
                language="en",
                diarize=False,
            ),
            conversion_options=TranscriptionConversionOptions(),
            import_into_library=False,
        )
        result = run_transcription_workflow(request, NullProgress())
        assert result.succeeded_count == 1
        assert result.failed_count == 1

    @patch("transcriptx.app.workflows.transcription.run_managed_import_workflow")
    @patch("transcriptx.app.workflows.transcription.get_provider")
    @patch("transcriptx.app.workflows.transcription.export_mp3_for_transcription")
    def test_import_failure_does_not_crash_batch(
        self, mock_convert, mock_get_provider, mock_import, tmp_path: Path
    ):
        wav = tmp_path / "meeting.wav"
        wav.write_bytes(b"wav")
        staged = tmp_path / "meeting.mp3"
        mock_convert.return_value = staged

        json_out = tmp_path / "json" / "meeting.json"
        json_out.parent.mkdir(parents=True)
        json_out.write_text("{}", encoding="utf-8")

        provider = MagicMock()
        provider.provider_id = "whispermlx"
        provider.transcribe.return_value = _provider_result(json_out)
        mock_get_provider.return_value = provider
        mock_import.side_effect = FileExistsError("collision")

        request = TranscriptionRequest(
            input_paths=[wav],
            transcription_options=TranscriptionOptions(
                provider_id="whispermlx",
                model="large-v3",
                language="en",
                diarize=False,
            ),
            conversion_options=TranscriptionConversionOptions(),
            import_into_library=True,
        )
        result = run_transcription_workflow(request, NullProgress())
        assert result.failed_count == 1
        assert result.file_results[0].import_success is False

    @patch("transcriptx.app.workflows.transcription.get_provider")
    @patch("transcriptx.app.workflows.transcription.export_mp3_for_transcription")
    @patch(
        "transcriptx.app.workflows.transcription._transcription_staging_dir",
    )
    @patch(
        "transcriptx.app.workflows.transcription._default_output_dir",
    )
    def test_cleanup_removes_staged_file_when_configured(
        self,
        mock_out_dir,
        mock_staging_dir,
        mock_convert,
        mock_get_provider,
        tmp_path: Path,
    ):
        data_dir = tmp_path / "data"
        mock_staging_dir.return_value = data_dir / "transcription" / "staging" / "job"
        mock_out_dir.return_value = data_dir / "transcription" / "output" / "job"

        wav = tmp_path / "meeting.wav"
        wav.write_bytes(b"wav")
        staged = mock_staging_dir.return_value / "meeting.mp3"
        staged.parent.mkdir(parents=True)
        staged.write_bytes(b"staged")
        mock_convert.return_value = staged

        json_out = mock_out_dir.return_value / "meeting" / "meeting.json"
        json_out.parent.mkdir(parents=True)
        json_out.write_text("{}", encoding="utf-8")

        provider = MagicMock()
        provider.provider_id = "whispermlx"
        provider.transcribe.return_value = _provider_result(json_out)
        mock_get_provider.return_value = provider

        request = TranscriptionRequest(
            input_paths=[wav],
            transcription_options=TranscriptionOptions(
                provider_id="whispermlx",
                model="large-v3",
                language="en",
                diarize=False,
            ),
            conversion_options=TranscriptionConversionOptions(),
            import_into_library=False,
            keep_intermediates=False,
        )
        run_transcription_workflow(request, NullProgress())
        assert not staged.exists()

    @patch("transcriptx.app.workflows.transcription.get_provider")
    @patch("transcriptx.app.workflows.transcription.export_mp3_for_transcription")
    @patch(
        "transcriptx.app.workflows.transcription._transcription_staging_dir",
    )
    @patch(
        "transcriptx.app.workflows.transcription._default_output_dir",
    )
    def test_keep_intermediates_preserves_staged_file(
        self,
        mock_out_dir,
        mock_staging_dir,
        mock_convert,
        mock_get_provider,
        tmp_path: Path,
    ):
        data_dir = tmp_path / "data"
        mock_staging_dir.return_value = data_dir / "transcription" / "staging" / "job"
        mock_out_dir.return_value = data_dir / "transcription" / "output" / "job"

        wav = tmp_path / "meeting.wav"
        wav.write_bytes(b"wav")
        staged = mock_staging_dir.return_value / "meeting.mp3"
        staged.parent.mkdir(parents=True)
        staged.write_bytes(b"staged")
        mock_convert.return_value = staged

        json_out = mock_out_dir.return_value / "meeting" / "meeting.json"
        json_out.parent.mkdir(parents=True)
        json_out.write_text("{}", encoding="utf-8")

        provider = MagicMock()
        provider.provider_id = "whispermlx"
        provider.transcribe.return_value = _provider_result(json_out)
        mock_get_provider.return_value = provider

        request = TranscriptionRequest(
            input_paths=[wav],
            transcription_options=TranscriptionOptions(
                provider_id="whispermlx",
                model="large-v3",
                language="en",
                diarize=False,
            ),
            conversion_options=TranscriptionConversionOptions(),
            import_into_library=False,
            keep_intermediates=True,
        )
        run_transcription_workflow(request, NullProgress())
        assert staged.exists()

    @patch("transcriptx.app.workflows.transcription.run_managed_import_workflow")
    @patch("transcriptx.app.workflows.transcription.get_provider")
    @patch("transcriptx.app.workflows.transcription.export_mp3_for_transcription")
    def test_preserves_raw_json_path_separate_from_import(
        self, mock_convert, mock_get_provider, mock_import, tmp_path: Path
    ):
        wav = tmp_path / "meeting.wav"
        wav.write_bytes(b"wav")
        staged = tmp_path / "meeting.mp3"
        mock_convert.return_value = staged

        raw_json = tmp_path / "provider_out.json"
        raw_json.write_text("{}", encoding="utf-8")
        imported = tmp_path / "library" / "meeting.json"
        mock_import.return_value = MagicMock(json_path=imported)

        provider = MagicMock()
        provider.provider_id = "whispermlx"
        provider.transcribe.return_value = _provider_result(raw_json)
        mock_get_provider.return_value = provider

        request = TranscriptionRequest(
            input_paths=[wav],
            transcription_options=TranscriptionOptions(
                provider_id="whispermlx",
                model="large-v3",
                language="en",
                diarize=False,
            ),
            conversion_options=TranscriptionConversionOptions(),
            import_into_library=True,
        )
        result = run_transcription_workflow(request, NullProgress())
        file_result = result.file_results[0]
        assert file_result.raw_json_path == raw_json
        assert file_result.imported_json_path == imported
        mock_import.assert_called_once()
        assert mock_import.call_args.kwargs["logical_upload_basename"] == "meeting.json"
