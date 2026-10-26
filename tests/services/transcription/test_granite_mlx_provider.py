"""Unit tests for Granite mlx-audio provider (stub + kwargs)."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.services.transcription.granite_mlx_provider import (
    CHUNK_TURBO_SECONDS,
    GRANITE_MODEL_OPTIONS,
    MODEL_ASR,
    MODEL_SAA,
    MODEL_TURBO,
    GraniteMLXProvider,
    build_gen_kwargs,
    chunk_seconds_for_model,
    is_turbo_ctc,
    resolve_granite_model,
)


def _opts(**overrides) -> TranscriptionOptions:
    values = dict(
        provider_id="granite_mlx",
        model="large-v3",
        language="en",
        diarize=False,
    )
    values.update(overrides)
    return TranscriptionOptions(**values)


@pytest.mark.unit
def test_resolve_model_follows_diarize() -> None:
    assert resolve_granite_model(_opts(diarize=False)) == MODEL_ASR
    assert resolve_granite_model(_opts(diarize=True)) == MODEL_SAA
    assert resolve_granite_model(_opts(model=MODEL_ASR, diarize=True)) == MODEL_SAA
    custom = "ibm-granite/granite-speech-custom"
    assert resolve_granite_model(_opts(model=custom, diarize=True)) == custom
    assert resolve_granite_model(_opts(model=MODEL_TURBO, diarize=True)) == MODEL_TURBO
    assert resolve_granite_model(_opts(model=MODEL_TURBO, diarize=False)) == MODEL_TURBO
    custom_turbo = "ibm-granite/granite-speech-5.0-470m-turboctc-local"
    assert (
        resolve_granite_model(_opts(model=custom_turbo, diarize=True)) == custom_turbo
    )
    assert GRANITE_MODEL_OPTIONS == (MODEL_ASR, MODEL_TURBO, MODEL_SAA)
    assert all("-nc" not in item for item in GRANITE_MODEL_OPTIONS)
    assert is_turbo_ctc(MODEL_TURBO)
    assert not is_turbo_ctc(MODEL_ASR)


@pytest.mark.unit
def test_chunk_seconds_turbo_is_longer() -> None:
    assert chunk_seconds_for_model(MODEL_TURBO, diarize=False) == CHUNK_TURBO_SECONDS
    assert chunk_seconds_for_model(MODEL_TURBO, diarize=True) == CHUNK_TURBO_SECONDS
    assert chunk_seconds_for_model(MODEL_ASR, diarize=False) == 110
    assert chunk_seconds_for_model(MODEL_SAA, diarize=False) == 300


@pytest.mark.unit
def test_gen_kwargs_hotwords_and_saa() -> None:
    kwargs = build_gen_kwargs(
        _opts(
            diarize=True,
            keyword_bias_enabled=True,
            keywords=("NATO", "FY26"),
        )
    )
    assert kwargs["task"] == "saa"
    assert kwargs["hotwords"] == ["NATO", "FY26"]
    assert kwargs["language"] is None
    asr = build_gen_kwargs(_opts(diarize=False, language="fr"))
    assert asr["punctuate"] is True
    assert asr["source_language"] == "fr"
    assert "hotwords" not in asr
    turbo = build_gen_kwargs(
        _opts(
            model=MODEL_TURBO,
            diarize=True,
            language="fr",
            keyword_bias_enabled=True,
            keywords=("NATO",),
        )
    )
    assert turbo == {}


@pytest.mark.unit
def test_stub_transcribe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_GRANITE_STUB", "1")
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"\x00")
    out = tmp_path / "out"
    provider = GraniteMLXProvider()
    opts = _opts(diarize=True)
    avail = provider.is_available(opts)
    assert avail.available
    result = provider.transcribe(audio, out, opts)
    assert result.success
    assert result.json_path is not None
    text = result.json_path.read_text(encoding="utf-8")
    assert "segments" in text
    assert "SPEAKER_00" in text or "speaker" in text.lower()


@pytest.mark.unit
def test_unavailable_off_mac_without_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRANSCRIPTX_GRANITE_STUB", raising=False)
    monkeypatch.setattr(
        "transcriptx.services.transcription.granite_mlx_provider.sys.platform",
        "linux",
    )
    provider = GraniteMLXProvider()
    avail = provider.is_available(_opts())
    assert not avail.available
    assert "macOS" in (avail.reason or "")


@pytest.mark.unit
def test_real_transcribe_mocks_ffmpeg_and_mlx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json as _json
    import subprocess as _sp
    from unittest.mock import patch

    from transcriptx.services.transcription import granite_mlx_provider as mod

    monkeypatch.delenv("TRANSCRIPTX_GRANITE_STUB", raising=False)
    audio = tmp_path / "meeting.wav"
    audio.write_bytes(b"\x00")
    out = tmp_path / "out"

    def fake_run(cmd, **kwargs):
        if "mlx_audio.stt.generate" in cmd:
            idx = cmd.index("--output-path")
            raw = Path(cmd[idx + 1])
            raw.parent.mkdir(parents=True, exist_ok=True)
            (raw.parent / "transcript.json").write_text(
                _json.dumps({"text": "hello NATO"}), encoding="utf-8"
            )
            assert any("hotwords" in part for part in cmd)
            return _sp.CompletedProcess(cmd, 0, stdout="ok", stderr="")
        dest = Path(cmd[-1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"wav")
        return _sp.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(
        mod, "resolve_mlx_audio_python", lambda env=None: "/fake/python"
    )
    monkeypatch.setattr(mod, "_ffmpeg_bin", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(mod, "_ffprobe_duration", lambda path: 2.0)
    with patch.object(mod.subprocess, "run", side_effect=fake_run):
        result = GraniteMLXProvider().transcribe(
            audio,
            out,
            _opts(
                diarize=False,
                keyword_bias_enabled=True,
                keywords=("NATO",),
            ),
        )
    assert result.success
    assert result.json_path is not None
    data = _json.loads(result.json_path.read_text(encoding="utf-8"))
    assert data["segments"][0]["text"] == "hello NATO"
    assert data["segments"][0]["start"] == 0.0
    assert data["segments"][0]["end"] == pytest.approx(2.0)


@pytest.mark.unit
def test_turbo_transcribe_omits_gen_kwargs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json as _json
    import subprocess as _sp
    from unittest.mock import patch

    from transcriptx.services.transcription import granite_mlx_provider as mod

    monkeypatch.delenv("TRANSCRIPTX_GRANITE_STUB", raising=False)
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"\x00")
    out = tmp_path / "out"
    seen: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        if "mlx_audio.stt.generate" in cmd:
            seen.append(list(cmd))
            idx = cmd.index("--output-path")
            raw = Path(cmd[idx + 1])
            raw.parent.mkdir(parents=True, exist_ok=True)
            (raw.parent / "transcript.json").write_text(
                _json.dumps({"text": "fast turbo"}), encoding="utf-8"
            )
            assert "--gen-kwargs" not in cmd
            assert MODEL_TURBO in cmd
            return _sp.CompletedProcess(cmd, 0, stdout="ok", stderr="")
        dest = Path(cmd[-1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"wav")
        return _sp.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(
        mod, "resolve_mlx_audio_python", lambda env=None: "/fake/python"
    )
    monkeypatch.setattr(mod, "_ffmpeg_bin", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(mod, "_ffprobe_duration", lambda path: 2.0)
    with patch.object(mod.subprocess, "run", side_effect=fake_run):
        result = GraniteMLXProvider().transcribe(
            audio,
            out,
            _opts(
                model=MODEL_TURBO,
                diarize=True,
                keyword_bias_enabled=True,
                keywords=("NATO",),
            ),
        )
    assert result.success
    assert result.json_path is not None
    assert seen
    assert "--gen-kwargs" not in seen[0]
    data = _json.loads(result.json_path.read_text(encoding="utf-8"))
    assert data["segments"][0]["text"] == "fast turbo"


@pytest.mark.unit
def test_availability_fails_without_mlx_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from transcriptx.services.transcription import granite_mlx_provider as mod

    monkeypatch.delenv("TRANSCRIPTX_GRANITE_STUB", raising=False)
    monkeypatch.setattr(mod.sys, "platform", "darwin")
    monkeypatch.setattr(mod, "resolve_mlx_audio_python", lambda env=None: None)
    monkeypatch.setattr(mod, "check_ffmpeg_available", lambda: (True, None))
    avail = GraniteMLXProvider().is_available(_opts())
    assert not avail.available
    assert "MLX_AUDIO_PYTHON" in (avail.reason or "")
