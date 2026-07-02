"""Additional unit tests for audio preprocessing helpers."""

from __future__ import annotations

import pytest

import transcriptx.core.audio.preprocessing as ap


@pytest.mark.unit
@pytest.mark.parametrize(
    ("global_mode", "per_step", "expected"),
    [
        ("selected", "auto", "auto"),
        ("selected", "off", "off"),
        ("auto", "off", "auto"),
        ("off", "auto", "off"),
    ],
)
def test_get_effective_mode(global_mode: str, per_step: str, expected: str) -> None:
    assert ap._get_effective_mode(global_mode, per_step) == expected


@pytest.mark.unit
def test_apply_preprocessing_noop_when_pydub_unavailable() -> None:
    fake_audio = object()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ap, "PYDUB_AVAILABLE", False)
        processed, steps = ap.apply_preprocessing(fake_audio)
    assert processed is fake_audio
    assert steps == []


@pytest.mark.unit
def test_check_audio_compliance_when_pydub_unavailable(tmp_path) -> None:
    audio_path = tmp_path / "a.wav"
    audio_path.write_bytes(b"fake")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ap, "PYDUB_AVAILABLE", False)
        result = ap.check_audio_compliance(audio_path)
    assert result["is_compliant"] is False
    assert result["missing_requirements"] == []
