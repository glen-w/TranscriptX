"""Tests for preprocessing assess."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

import transcriptx.core.audio.preprocessing as ap


class _FakeAudio:
    def __init__(self, *, channels=1, frame_rate=16000, sample_width=2, samples=None):
        self.channels = channels
        self.frame_rate = frame_rate
        self.sample_width = sample_width
        self._samples = samples if samples is not None else [0, 1, -1] * 100

    def get_array_of_samples(self):
        return self._samples


@pytest.mark.unit
def test_assess_audio_noise_returns_default_when_pydub_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(ap, "PYDUB_AVAILABLE", False)
    out = ap.assess_audio_noise(Path("/tmp/a.wav"))
    assert out["noise_level"] == "low"
    assert out["suggested_steps"] == []


@pytest.mark.unit
def test_assess_audio_noise_populates_metrics_and_suggestions(
    monkeypatch: pytest.MonkeyPatch,
):
    loud = [32767, -32768] * 200
    fake = _FakeAudio(channels=2, frame_rate=8000, sample_width=2, samples=loud)

    monkeypatch.setattr(ap, "PYDUB_AVAILABLE", True)
    monkeypatch.setattr(ap, "WEBRTCVAD_AVAILABLE", False)
    monkeypatch.setattr(ap, "SOUNDFILE_AVAILABLE", False)
    monkeypatch.setattr(ap, "AudioSegment", SimpleNamespace(from_file=lambda _p: fake))

    out = ap.assess_audio_noise(Path("/tmp/a.wav"))

    assert out["noise_level"] in {"medium", "high"}
    assert "normalize" in out["suggested_steps"]
    # non-16k + stereo should prepend resample/mono suggestions
    assert "resample" in out["suggested_steps"]
    assert "mono" in out["suggested_steps"]
    assert isinstance(out["metrics"]["rms_db"], float)


@pytest.mark.unit
def test_assess_audio_noise_handles_decode_errors(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ap, "PYDUB_AVAILABLE", True)
    monkeypatch.setattr(
        ap,
        "AudioSegment",
        SimpleNamespace(
            from_file=lambda _p: (_ for _ in ()).throw(ValueError("decode"))
        ),
    )

    out = ap.assess_audio_noise(Path("/tmp/bad.wav"))
    assert out["noise_level"] == "low"
    assert out["suggested_steps"] == []
