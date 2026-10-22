"""Unit tests for Parakeet Docker provider (stub mode + mocked docker run)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.services.transcription.parakeet_docker_provider import (
    ParakeetDockerProvider,
)
from transcriptx.services.transcription.parakeet_recipe import (
    INNER_SCRIPT_NAME,
    PARAKEET_MODEL_DEFAULT,
    build_parakeet_docker_argv,
    write_parakeet_inner_script,
)


@pytest.mark.unit
def test_parakeet_stub_transcribe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRANSCRIPTX_PARAKEET_STUB", "1")
    audio = tmp_path / "clip.mp3"
    audio.write_bytes(b"\x00")
    out = tmp_path / "out"
    provider = ParakeetDockerProvider()
    opts = TranscriptionOptions(
        provider_id="parakeet_docker",
        model="nvidia/parakeet-tdt-0.6b-v3",
        language="en",
        diarize=False,
        device="cpu",
    )
    avail = provider.is_available(opts)
    assert avail.available
    result = provider.transcribe(audio, out, opts)
    assert result.success
    assert result.json_path is not None
    assert result.json_path.is_file()


@pytest.mark.unit
def test_parakeet_docker_argv_contains_python_script_and_gpus(tmp_path: Path) -> None:
    audio = tmp_path / "meeting.mp3"
    audio.write_bytes(b"\x00")
    out = tmp_path / "out"
    out.mkdir()
    write_parakeet_inner_script(out)
    argv = build_parakeet_docker_argv(
        docker_binary="/usr/bin/docker",
        image="nvcr.io/nvidia/nemo:24.07.1",
        audio_path=audio,
        output_dir=out,
        model=PARAKEET_MODEL_DEFAULT,
        device="cuda",
    )
    assert argv[0] == "/usr/bin/docker"
    assert argv[1:3] == ["run", "--rm"]
    assert "--gpus" in argv and "all" in argv
    assert f"{audio.parent}:/audio:ro" in argv
    assert f"{out.resolve()}:/output" in argv
    assert "python" in argv
    assert f"/output/{INNER_SCRIPT_NAME}" in argv
    assert "/audio/meeting.mp3" in argv
    assert "/output/meeting.jsonl" in argv
    assert PARAKEET_MODEL_DEFAULT in argv
    script = (out / INNER_SCRIPT_NAME).read_text(encoding="utf-8")
    assert "ASRModel.from_pretrained" in script
    assert "timestamps=True" in script


@pytest.mark.unit
def test_parakeet_production_transcribe_converts_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TRANSCRIPTX_PARAKEET_STUB", raising=False)
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"\x00")
    out = tmp_path / "out"

    def _fake_run(cmd, **_kwargs):
        jsonl = out / "clip.jsonl"
        jsonl.write_text(
            '{"start": 0.0, "end": 1.5, "text": "hello from parakeet"}\n',
            encoding="utf-8",
        )
        assert "python" in cmd
        assert "/output/_parakeet_transcribe.py" in cmd
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(
        "transcriptx.services.transcription.parakeet_docker_provider.resolve_docker_binary",
        lambda: Path("/usr/bin/docker"),
    )
    monkeypatch.setattr(
        "transcriptx.services.transcription.parakeet_docker_provider.subprocess.run",
        _fake_run,
    )
    provider = ParakeetDockerProvider()
    opts = TranscriptionOptions(
        provider_id="parakeet_docker",
        model="nvidia/parakeet-tdt-0.6b-v3",
        language="en",
        diarize=False,
        device="cuda",
    )
    result = provider.transcribe(audio, out, opts)
    assert result.success
    assert result.json_path is not None
    payload = result.json_path.read_text(encoding="utf-8")
    assert "hello from parakeet" in payload
    assert (out / INNER_SCRIPT_NAME).is_file()


@pytest.mark.unit
def test_parakeet_docker_argv_rejects_flag_image(tmp_path: Path) -> None:
    audio = tmp_path / "meeting.mp3"
    audio.write_bytes(b"\x00")
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError, match="unsafe Parakeet image"):
        build_parakeet_docker_argv(
            docker_binary="/usr/bin/docker",
            image="--network=host",
            audio_path=audio,
            output_dir=out,
            model=PARAKEET_MODEL_DEFAULT,
        )
    with pytest.raises(ValueError, match="unsafe Parakeet model"):
        build_parakeet_docker_argv(
            docker_binary="/usr/bin/docker",
            image="nvcr.io/nvidia/nemo:24.07.1",
            audio_path=audio,
            output_dir=out,
            model="-e FOO=bar",
        )


@pytest.mark.unit
def test_parakeet_missing_docker_does_not_succeed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TRANSCRIPTX_PARAKEET_STUB", raising=False)
    monkeypatch.setattr(
        "transcriptx.services.transcription.parakeet_docker_provider.resolve_docker_binary",
        lambda: None,
    )
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"\x00")
    provider = ParakeetDockerProvider()
    opts = TranscriptionOptions(
        provider_id="parakeet_docker",
        model="nvidia/parakeet-tdt-0.6b-v3",
        language="en",
        diarize=False,
        device="cpu",
    )
    result = provider.transcribe(audio, tmp_path / "out", opts)
    assert result.success is False
    assert "docker" in (result.error or "").lower()


@pytest.mark.unit
def test_parakeet_nonzero_exit_and_missing_jsonl_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TRANSCRIPTX_PARAKEET_STUB", raising=False)
    monkeypatch.setattr(
        "transcriptx.services.transcription.parakeet_docker_provider.resolve_docker_binary",
        lambda: Path("/usr/bin/docker"),
    )
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"\x00")
    out = tmp_path / "out"
    provider = ParakeetDockerProvider()
    opts = TranscriptionOptions(
        provider_id="parakeet_docker",
        model="nvidia/parakeet-tdt-0.6b-v3",
        language="en",
        diarize=False,
        device="cpu",
    )

    monkeypatch.setattr(
        "transcriptx.services.transcription.parakeet_docker_provider.subprocess.run",
        lambda *_a, **_k: SimpleNamespace(returncode=2, stdout="", stderr="boom"),
    )
    failed = provider.transcribe(audio, out, opts)
    assert failed.success is False
    assert failed.returncode == 2

    monkeypatch.setattr(
        "transcriptx.services.transcription.parakeet_docker_provider.subprocess.run",
        lambda *_a, **_k: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )
    missing = provider.transcribe(audio, out, opts)
    assert missing.success is False
    assert "JSON" in (missing.error or "") or "json" in (missing.error or "").lower()
