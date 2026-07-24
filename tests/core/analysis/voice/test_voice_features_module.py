"""Unit tests for VoiceFeaturesAnalysis.run_from_context (gating and happy path)."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.voice_features import VoiceFeaturesAnalysis


@pytest.fixture
def voice_context(tmp_path: Path) -> SimpleNamespace:
    tdir = tmp_path / "out" / "meet"
    tdir.mkdir(parents=True)
    tp = tmp_path / "meet.json"
    tp.write_text("[]", encoding="utf-8")
    stored: list[tuple[str, object]] = []

    def _store(name: str, payload: object) -> None:
        stored.append((name, payload))

    return SimpleNamespace(
        transcript_path=str(tp),
        _stored=stored,
        get_transcript_dir=lambda: str(tdir),
        get_run_id=lambda: "run_test",
        get_runtime_flags=lambda: {},
        store_analysis_result=_store,
    )


@patch("transcriptx.core.analysis.voice_features.check_voice_optional_deps")
def test_voice_features_skips_when_optional_deps_missing(
    mock_deps: MagicMock, voice_context: SimpleNamespace
) -> None:
    mock_deps.return_value = {
        "ok": False,
        "missing_optional_deps": ["librosa"],
        "install_hint": (
            "pip install -e '.[voice]' (from a TranscriptX git checkout; not on PyPI)"
        ),
    }

    out_svc = MagicMock()
    out_svc.get_artifacts.return_value = [{"path": "a.json"}]

    with patch(
        "transcriptx.core.analysis.voice_features.create_output_service",
        return_value=out_svc,
    ):
        result = VoiceFeaturesAnalysis().run_from_context(voice_context)

    assert result["status"] == "success"
    assert result["payload"]["status"] == "skipped"
    assert result["payload"]["skipped_reason"] == "missing_optional_deps"
    assert result["metrics"]["skipped_reason"] == "missing_optional_deps"
    out_svc.save_data.assert_called()
    call_kw = out_svc.save_data.call_args_list[0]
    assert call_kw[0][1] == "voice_features_locator"
    assert call_kw[1].get("format_type") == "json"


@patch("transcriptx.core.analysis.voice_features.check_voice_optional_deps")
@patch("transcriptx.core.analysis.voice_features.load_or_compute_voice_features")
def test_voice_features_success_records_locator_and_artifacts(
    mock_load: MagicMock,
    mock_deps: MagicMock,
    voice_context: SimpleNamespace,
    tmp_path: Path,
) -> None:
    mock_deps.return_value = {
        "ok": True,
        "missing_optional_deps": [],
        "install_hint": "",
    }
    core_file = tmp_path / "core.parquet"
    core_file.write_bytes(b"x")
    mock_load.return_value = {
        "voice_feature_core_path": str(core_file),
        "meta": {"cache_hit": True},
    }

    out_svc = MagicMock()
    out_svc.get_artifacts.return_value = []

    with patch(
        "transcriptx.core.analysis.voice_features.create_output_service",
        return_value=out_svc,
    ):
        result = VoiceFeaturesAnalysis().run_from_context(voice_context)

    assert result["status"] == "success"
    assert result["payload"]["meta"]["cache_hit"] is True
    assert out_svc.save_data.call_count >= 1
    names = [c[0][1] for c in out_svc.save_data.call_args_list]
    assert "voice_features_locator" in names
    out_svc._record_artifact.assert_called()


@patch("transcriptx.core.analysis.voice_features.check_voice_optional_deps")
@patch("transcriptx.core.analysis.voice_features.load_or_compute_voice_features")
def test_voice_features_error_returns_module_error_envelope(
    mock_load: MagicMock,
    mock_deps: MagicMock,
    voice_context: SimpleNamespace,
) -> None:
    mock_deps.return_value = {
        "ok": True,
        "missing_optional_deps": [],
        "install_hint": "",
    }
    mock_load.side_effect = RuntimeError("audio failed")

    out_svc = MagicMock()

    with patch(
        "transcriptx.core.analysis.voice_features.create_output_service",
        return_value=out_svc,
    ):
        result = VoiceFeaturesAnalysis().run_from_context(voice_context)

    assert result["status"] == "error"
    assert result.get("error") is not None
    assert result["error"]["error_type"] == "RuntimeError"
