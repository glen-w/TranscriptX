"""Tests for voice extract heavy."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.analysis.voice import extract as ve


class _Ctx:
    def __init__(self, segments):
        self._segments = segments
        self.transcript_path = "/tmp/demo.json"

    def get_segments(self):
        return self._segments

    def get_transcript_key(self):
        return "demo"

    def get_transcript_dir(self):
        return "/tmp"


class _Svc:
    base_name = "demo"

    def get_output_structure(self):
        return SimpleNamespace(global_data_dir="/tmp")


@pytest.mark.heavy
@pytest.mark.slow
def test_load_or_compute_voice_features_skips_when_voice_disabled(monkeypatch) -> None:
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(voice=SimpleNamespace(enabled=False))
    )
    monkeypatch.setattr(ve, "get_config", lambda: cfg)
    result = ve.load_or_compute_voice_features(
        context=_Ctx([{"start": 0.0, "end": 1.0}]),
        output_service=_Svc(),
    )
    assert result["status"] == "skipped"
    assert result["skipped_reason"] == "disabled"


@pytest.mark.heavy
@pytest.mark.slow
def test_load_or_compute_voice_features_skips_when_timestamps_missing(
    monkeypatch,
) -> None:
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(voice=SimpleNamespace(enabled=True)),
    )
    monkeypatch.setattr(ve, "get_config", lambda: cfg)
    result = ve.load_or_compute_voice_features(
        context=_Ctx([{"start": 0.0, "text": "missing end"}]),
        output_service=_Svc(),
    )
    assert result["status"] == "skipped"
    assert result["skipped_reason"] == "missing_timestamps"


@pytest.mark.heavy
@pytest.mark.slow
def test_load_or_compute_voice_features_skips_when_audio_missing(monkeypatch) -> None:
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            voice=SimpleNamespace(
                enabled=True,
                sample_rate=16000,
                vad_mode=2,
                pad_s=0.1,
                max_seconds_for_pitch=5.0,
                egemaps_enabled=False,
                deep_mode=False,
                deep_model_name="x",
                deep_max_seconds=1.0,
                store_parquet="auto",
                strict_audio_hash=False,
                max_segments_considered=None,
            )
        )
    )
    monkeypatch.setattr(ve, "get_config", lambda: cfg)
    monkeypatch.setattr(ve, "resolve_audio_path", lambda **_kwargs: None)
    result = ve.load_or_compute_voice_features(
        context=_Ctx([{"start": 0.0, "end": 1.0, "text": "ok"}]),
        output_service=_Svc(),
    )
    assert result["status"] == "skipped"
    assert result["skipped_reason"] == "no_audio"
