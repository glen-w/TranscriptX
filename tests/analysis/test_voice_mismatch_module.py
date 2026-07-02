"""Unit tests for VoiceMismatchAnalysis module entry points."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.voice_mismatch import VoiceMismatchAnalysis


@pytest.mark.unit
def test_analyze_returns_empty_dict() -> None:
    module = VoiceMismatchAnalysis()
    assert module.analyze([], speaker_map={}) == {}


@pytest.mark.unit
def test_run_from_context_skips_when_voice_features_missing(tmp_path) -> None:
    module = VoiceMismatchAnalysis()
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_transcript_dir.return_value = tmp_path
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}
    context.get_analysis_result.return_value = {
        "status": "skipped",
        "skipped_reason": "no_voice_features",
    }

    fake_service = MagicMock()
    fake_service.get_artifacts.return_value = [{"id": "locator"}]

    with (
        patch(
            "transcriptx.core.analysis.voice_mismatch.create_output_service",
            return_value=fake_service,
        ),
        patch("transcriptx.core.analysis.voice_mismatch.log_analysis_start"),
        patch("transcriptx.core.analysis.voice_mismatch.log_analysis_complete"),
    ):
        result = module.run_from_context(context)

    assert result["status"] == "success"
    assert result["metrics"]["skipped_reason"] == "no_voice_features"
    fake_service.save_data.assert_called_once()
    saved_payload = fake_service.save_data.call_args[0][0]
    assert saved_payload["status"] == "skipped"
