"""Tests for load_audio_segment ADPCM / pydub fallback."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.core.audio import utils as audio_utils


class _FakeAudio:
    def __init__(self, *, channels=1, frame_rate=16000, sample_width=2):
        self.channels = channels
        self.frame_rate = frame_rate
        self.sample_width = sample_width

    def get_array_of_samples(self):
        return [0, 1, -1] * 100


@pytest.mark.unit
def test_load_audio_segment_uses_pydub_when_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = _FakeAudio()
    audio_path = tmp_path / "plain.wav"
    audio_path.write_bytes(b"not-a-real-wav")

    monkeypatch.setattr(
        audio_utils,
        "AudioSegment",
        SimpleNamespace(from_file=lambda _p: fake),
    )

    loaded = audio_utils.load_audio_segment(audio_path)
    assert loaded is fake


@pytest.mark.unit
def test_load_audio_segment_falls_back_to_ffmpeg_on_decode_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from pydub.exceptions import CouldntDecodeError

    audio_path = tmp_path / "adpcm.wav"
    audio_path.write_bytes(b"fake")

    def _raise_decode(_path: str):
        raise CouldntDecodeError("pcm_s4le missing")

    monkeypatch.setattr(
        audio_utils,
        "AudioSegment",
        SimpleNamespace(
            from_file=_raise_decode,
            from_wav=lambda buf: _FakeAudio(frame_rate=48000),
        ),
    )
    monkeypatch.setattr(
        "transcriptx.core.audio.tools._find_ffmpeg_path",
        lambda: "/usr/bin/ffmpeg",
    )

    captured: dict[str, list[str]] = {}

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return SimpleNamespace(returncode=0, stdout=_minimal_wav_bytes(), stderr=b"")

    monkeypatch.setattr(audio_utils.subprocess, "run", _fake_run)

    loaded = audio_utils.load_audio_segment(audio_path)

    assert captured["cmd"][:3] == ["/usr/bin/ffmpeg", "-y", "-i"]
    assert "-acodec" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("-acodec") + 1] == "pcm_s16le"
    assert loaded.frame_rate == 48000


def _minimal_wav_bytes() -> bytes:
    import io

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        wf.writeframes(b"\x00\x00" * 100)
    return buf.getvalue()


@pytest.mark.integration
def test_load_audio_segment_decodes_adpcm_ima_wav(tmp_path: Path) -> None:
    if not shutil_which("ffmpeg"):
        pytest.skip("ffmpeg not available")

    src = tmp_path / "tone.wav"
    adpcm = tmp_path / "adpcm.wav"

    tone = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.2",
            "-ac",
            "1",
            "-ar",
            "48000",
            str(src),
        ],
        capture_output=True,
        check=False,
    )
    if tone.returncode != 0:
        pytest.skip("ffmpeg lavfi unavailable")

    encoded = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-acodec",
            "adpcm_ima_wav",
            str(adpcm),
        ],
        capture_output=True,
        check=False,
    )
    if encoded.returncode != 0:
        pytest.skip("ffmpeg adpcm_ima_wav encoder unavailable")

    with pytest.raises(Exception):
        from pydub import AudioSegment

        AudioSegment.from_file(str(adpcm))

    loaded = audio_utils.load_audio_segment(adpcm)
    assert loaded.frame_rate == 48000
    assert loaded.channels == 1
    assert len(loaded) > 0


def shutil_which(cmd: str) -> str | None:
    import shutil

    return shutil.which(cmd)
