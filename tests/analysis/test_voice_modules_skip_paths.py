"""Skip-path contract tests for voice analysis modules."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.voice.contours import VoiceContoursAnalysis
from transcriptx.core.analysis.voice_fingerprint import VoiceFingerprintAnalysis
from transcriptx.core.analysis.voice_mismatch import VoiceMismatchAnalysis
from transcriptx.core.analysis.voice_tension import VoiceTensionAnalysis


def _context(tmp_path):
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_transcript_dir.return_value = tmp_path
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}
    return context


@pytest.mark.unit
@pytest.mark.parametrize(
    ("module_cls", "locator_name"),
    [
        (VoiceMismatchAnalysis, "voice_mismatch_locator"),
        (VoiceTensionAnalysis, "voice_tension_locator"),
        (VoiceFingerprintAnalysis, "voice_fingerprint_locator"),
    ],
)
def test_voice_modules_skip_without_features(
    tmp_path, module_cls, locator_name: str
) -> None:
    module = module_cls()
    context = _context(tmp_path)
    context.get_analysis_result.return_value = {
        "status": "skipped",
        "skipped_reason": "no_voice_features",
    }
    fake_service = MagicMock()
    fake_service.get_artifacts.return_value = []

    with (
        patch(
            f"{module_cls.__module__}.create_output_service",
            return_value=fake_service,
        ),
        patch(f"{module_cls.__module__}.log_analysis_start"),
        patch(f"{module_cls.__module__}.log_analysis_complete"),
    ):
        result = module.run_from_context(context)

    assert result["status"] == "success"
    assert result["metrics"]["skipped_reason"] == "no_voice_features"
    fake_service.save_data.assert_called_once()
    assert fake_service.save_data.call_args[0][1] == locator_name


@pytest.mark.unit
def test_voice_contours_skips_when_optional_deps_missing(tmp_path) -> None:
    module = VoiceContoursAnalysis()
    context = _context(tmp_path)
    fake_service = MagicMock()
    fake_service.get_artifacts.return_value = []

    with (
        patch(
            "transcriptx.core.analysis.voice.contours.create_output_service",
            return_value=fake_service,
        ),
        patch(
            "transcriptx.core.analysis.voice.contours.check_voice_optional_deps",
            return_value={
                "ok": False,
                "missing_optional_deps": ["librosa"],
                "install_hint": "pip install librosa",
            },
        ),
        patch("transcriptx.core.analysis.voice.contours.log_analysis_start"),
        patch("transcriptx.core.analysis.voice.contours.log_analysis_complete"),
    ):
        result = module.run_from_context(context)

    assert result["status"] == "success"
    assert result["metrics"]["skipped_reason"] == "missing_optional_deps"


@pytest.mark.unit
def test_voice_contours_skips_when_no_audio(tmp_path) -> None:
    module = VoiceContoursAnalysis()
    context = _context(tmp_path)
    context.get_analysis_result.return_value = {
        "status": "ok",
        "voice_feature_core_path": str(tmp_path / "core.parquet"),
    }
    fake_service = MagicMock()
    fake_service.get_artifacts.return_value = []

    with (
        patch(
            "transcriptx.core.analysis.voice.contours.create_output_service",
            return_value=fake_service,
        ),
        patch(
            "transcriptx.core.analysis.voice.contours.check_voice_optional_deps",
            return_value={"ok": True},
        ),
        patch(
            "transcriptx.core.analysis.voice.contours.load_voice_features",
            return_value=__import__("pandas").DataFrame(
                {
                    "speaker": ["Alice"],
                    "duration_s": [5.0],
                    "segment_id": ["s1"],
                    "start": [0.0],
                    "end": [5.0],
                }
            ),
        ),
        patch(
            "transcriptx.core.analysis.voice.contours.resolve_audio_path",
            return_value=None,
        ),
        patch("transcriptx.core.analysis.voice.contours.log_analysis_start"),
        patch("transcriptx.core.analysis.voice.contours.log_analysis_complete"),
    ):
        result = module.run_from_context(context)

    assert result["status"] == "success"
    payload = fake_service.save_data.call_args[0][0]
    assert payload["skipped_reason"] == "no_audio"
