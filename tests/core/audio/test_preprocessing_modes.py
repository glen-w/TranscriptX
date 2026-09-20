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


@pytest.mark.unit
def test_normalize_loudness_unlinks_temp_on_failure(monkeypatch) -> None:
    """SR-07: pyloudnorm path must not leave delete=False WAVs after errors."""
    if not ap.PYDUB_AVAILABLE:
        pytest.skip("pydub unavailable")

    from pydub import AudioSegment

    audio = AudioSegment.silent(duration=200, frame_rate=16000)
    created: list[str] = []
    real_named = __import__("tempfile").NamedTemporaryFile

    def tracking_named(*args, **kwargs):
        kwargs["delete"] = False
        handle = real_named(*args, **kwargs)
        created.append(handle.name)
        return handle

    def boom(*_args, **_kwargs):
        raise RuntimeError("forced loudness failure")

    monkeypatch.setattr(ap, "PYLoudnorm_AVAILABLE", True)
    monkeypatch.setattr(ap, "SOUNDFILE_AVAILABLE", True)
    monkeypatch.setattr("tempfile.NamedTemporaryFile", tracking_named)
    monkeypatch.setattr(ap, "sf", type("SF", (), {"read": boom, "write": boom})())

    result = ap.normalize_loudness(audio)
    assert result is not None
    assert created, "expected a temp WAV to be created"
    for path in created:
        assert not __import__("os").path.exists(path), path


@pytest.mark.unit
def test_denoise_audio_unlinks_temp_on_failure(monkeypatch) -> None:
    """SR-07: noisereduce path must not leave delete=False WAVs after errors."""
    if not ap.PYDUB_AVAILABLE:
        pytest.skip("pydub unavailable")

    from pydub import AudioSegment

    audio = AudioSegment.silent(duration=200, frame_rate=16000)
    created: list[str] = []
    real_named = __import__("tempfile").NamedTemporaryFile

    def tracking_named(*args, **kwargs):
        kwargs["delete"] = False
        handle = real_named(*args, **kwargs)
        created.append(handle.name)
        return handle

    def boom(*_args, **_kwargs):
        raise RuntimeError("forced denoise failure")

    monkeypatch.setattr(ap, "NOISEREDUCE_AVAILABLE", True)
    monkeypatch.setattr(ap, "SOUNDFILE_AVAILABLE", True)
    monkeypatch.setattr("tempfile.NamedTemporaryFile", tracking_named)
    monkeypatch.setattr(ap, "sf", type("SF", (), {"read": boom, "write": boom})())

    result = ap.denoise_audio(audio)
    assert result is not None
    assert created, "expected a temp WAV to be created"
    for path in created:
        assert not __import__("os").path.exists(path), path
