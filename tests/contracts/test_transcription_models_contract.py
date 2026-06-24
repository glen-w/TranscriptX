"""Contract tests for transcription request/result dataclasses."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from transcriptx.app.models.requests import (
    TranscriptionConversionOptions,
    TranscriptionOptions,
    TranscriptionRequest,
)
from transcriptx.app.models.results import (
    TranscriptionBatchResult,
    TranscriptionFileResult,
    TranscriptionProviderResult,
)


@pytest.mark.contract
class TestTranscriptionModelsContract:
    def test_frozen_options_dataclasses(self):
        conv = TranscriptionConversionOptions()
        opts = TranscriptionOptions(
            provider_id="whispermlx",
            model="large-v3",
            language="en",
            diarize=False,
        )
        with pytest.raises(Exception):
            conv.bitrate = "192k"  # type: ignore[misc]
        with pytest.raises(Exception):
            opts.model = "tiny"  # type: ignore[misc]

    def test_transcription_options_field_names_exclude_secrets(self):
        names = {f.name for f in fields(TranscriptionOptions)}
        assert "hf_token" not in names
        assert "HF_TOKEN" not in names

    def test_provider_result_has_required_debug_fields(self):
        names = {f.name for f in fields(TranscriptionProviderResult)}
        assert {"output_dir", "returncode", "duration_seconds", "stderr_tail"} <= names

    def test_file_result_tracks_staging_and_paths(self):
        names = {f.name for f in fields(TranscriptionFileResult)}
        assert {
            "created_staged_file",
            "raw_json_path",
            "imported_json_path",
            "provider_id",
        } <= names

    def test_request_keep_intermediates_not_on_conversion_options(self):
        conv_names = {f.name for f in fields(TranscriptionConversionOptions)}
        req_names = {f.name for f in fields(TranscriptionRequest)}
        assert "keep_intermediates" not in conv_names
        assert "keep_intermediates" in req_names

    def test_provider_result_tuple_tails(self):
        result = TranscriptionProviderResult(
            success=True,
            json_path=Path("a.json"),
            output_dir=Path("out"),
            returncode=0,
            stdout_tail=("line",),
            stderr_tail=(),
            duration_seconds=1.0,
        )
        assert isinstance(result.stdout_tail, tuple)

    def test_batch_result_shape(self):
        result = TranscriptionBatchResult(
            job_id="job",
            success=True,
            file_results=[],
            succeeded_count=0,
            failed_count=0,
            output_dir=Path("out"),
            duration_seconds=0.0,
        )
        assert result.duration_seconds == 0.0
