"""Tests for WhisperMLX provider."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.services.transcription.whispermlx_provider import (
    WhisperMLXProvider,
    _discover_json,
    resolve_whispermlx_binary,
)


@pytest.mark.unit
class TestWhisperMLXAvailability:
    @patch.dict("os.environ", {}, clear=True)
    @patch("transcriptx.services.transcription.whispermlx_provider.sys.platform", "linux")
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.check_ffmpeg_available",
        return_value=(True, None),
    )
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.resolve_whispermlx_binary",
        return_value=Path("/usr/bin/whispermlx"),
    )
    def test_unavailable_on_non_macos(self, *_mocks):
        provider = WhisperMLXProvider()
        options = TranscriptionOptions(
            provider_id="whispermlx",
            model="large-v3",
            language="en",
            diarize=False,
        )
        availability = provider.is_available(options)
        assert not availability.available

    @patch.dict("os.environ", {}, clear=True)
    @patch("transcriptx.services.transcription.whispermlx_provider.sys.platform", "darwin")
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.check_ffmpeg_available",
        return_value=(True, None),
    )
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.resolve_whispermlx_binary",
        return_value=None,
    )
    def test_unavailable_when_binary_missing(self, *_mocks):
        provider = WhisperMLXProvider()
        options = TranscriptionOptions(
            provider_id="whispermlx",
            model="large-v3",
            language="en",
            diarize=False,
        )
        assert not provider.is_available(options).available

    @patch("transcriptx.services.transcription.whispermlx_provider.sys.platform", "darwin")
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.check_ffmpeg_available",
        return_value=(True, None),
    )
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.resolve_whispermlx_binary",
        return_value=Path("/usr/bin/whispermlx"),
    )
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.get_secret",
        return_value=None,
    )
    def test_unavailable_when_diarize_on_and_token_missing(self, *_mocks):
        provider = WhisperMLXProvider()
        options = TranscriptionOptions(
            provider_id="whispermlx",
            model="large-v3",
            language="en",
            diarize=True,
        )
        assert not provider.is_available(options).available

    @patch("transcriptx.services.transcription.whispermlx_provider.sys.platform", "darwin")
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.check_ffmpeg_available",
        return_value=(True, None),
    )
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.resolve_whispermlx_binary",
        return_value=Path("/usr/bin/whispermlx"),
    )
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.get_secret",
        return_value=None,
    )
    def test_available_when_diarize_off_without_token(self, *_mocks):
        provider = WhisperMLXProvider()
        options = TranscriptionOptions(
            provider_id="whispermlx",
            model="large-v3",
            language="en",
            diarize=False,
        )
        assert provider.is_available(options).available

    @patch("transcriptx.services.transcription.whispermlx_provider.sys.platform", "darwin")
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.check_ffmpeg_available",
        return_value=(True, None),
    )
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.resolve_whispermlx_binary",
        return_value=Path("/usr/bin/whispermlx"),
    )
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.get_secret",
        side_effect=lambda name, env=None: "hf_secret" if name == "HF_TOKEN" else None,
    )
    def test_unavailable_after_toggling_diarize_on(self, *_mocks):
        provider = WhisperMLXProvider()
        off = TranscriptionOptions(
            provider_id="whispermlx",
            model="large-v3",
            language="en",
            diarize=False,
        )
        on = TranscriptionOptions(
            provider_id="whispermlx",
            model="large-v3",
            language="en",
            diarize=True,
        )
        assert provider.is_available(off).available
        with patch(
            "transcriptx.services.transcription.whispermlx_provider.get_secret",
            return_value=None,
        ):
            assert not provider.is_available(on).available


@pytest.mark.unit
class TestWhisperMLXTranscribe:
    @patch("transcriptx.services.transcription.whispermlx_provider.subprocess.Popen")
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.resolve_whispermlx_binary",
        return_value=Path("/usr/bin/whispermlx"),
    )
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.get_secret",
        return_value="hf_secret_token",
    )
    def test_command_includes_diarize_only_when_enabled(
        self, _mock_secret, _mock_binary, mock_popen, tmp_path: Path
    ):
        audio = tmp_path / "clip.mp3"
        audio.write_bytes(b"x")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        proc = MagicMock()
        proc.communicate.return_value = ("", "")
        proc.returncode = 0
        mock_popen.return_value = proc

        provider = WhisperMLXProvider()
        options_off = TranscriptionOptions(
            provider_id="whispermlx",
            model="large-v3",
            language="en",
            diarize=False,
        )
        (out_dir / "clip.json").write_text("{}", encoding="utf-8")
        provider.transcribe(audio, out_dir, options_off)
        cmd_off = mock_popen.call_args[0][0]
        assert "--diarize" not in cmd_off

        options_on = TranscriptionOptions(
            provider_id="whispermlx",
            model="large-v3",
            language="en",
            diarize=True,
        )
        provider.transcribe(audio, out_dir, options_on)
        cmd_on = mock_popen.call_args[0][0]
        assert "--diarize" in cmd_on
        assert "hf_secret_token" not in cmd_on

    @patch("transcriptx.services.transcription.whispermlx_provider.subprocess.Popen")
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.resolve_whispermlx_binary",
        return_value=Path("/usr/bin/whispermlx"),
    )
    def test_token_redacted_from_logs(self, _mock_binary, mock_popen, tmp_path: Path):
        audio = tmp_path / "clip.mp3"
        audio.write_bytes(b"x")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "clip.json").write_text("{}", encoding="utf-8")
        proc = MagicMock()
        proc.communicate.return_value = ("output hf_secret_token", "err hf_secret_token")
        proc.returncode = 0
        mock_popen.return_value = proc

        with patch(
            "transcriptx.services.transcription.whispermlx_provider.get_secret",
            return_value="hf_secret_token",
        ):
            provider = WhisperMLXProvider()
            options = TranscriptionOptions(
                provider_id="whispermlx",
                model="large-v3",
                language="en",
                diarize=True,
            )
            result = provider.transcribe(audio, out_dir, options)

        joined = "\n".join(result.stdout_tail + result.stderr_tail)
        assert "hf_secret_token" not in joined

    @patch("transcriptx.services.transcription.whispermlx_provider.subprocess.Popen")
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.resolve_whispermlx_binary",
        return_value=Path("/usr/bin/whispermlx"),
    )
    def test_timeout_kills_process(self, _mock_binary, mock_popen, tmp_path: Path):
        import subprocess as sp

        audio = tmp_path / "clip.mp3"
        audio.write_bytes(b"x")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        proc = MagicMock()
        proc.communicate.side_effect = [
            sp.TimeoutExpired(cmd="whispermlx", timeout=1),
            ("", "timed out"),
        ]
        proc.returncode = -9
        mock_popen.return_value = proc

        provider = WhisperMLXProvider()
        options = TranscriptionOptions(
            provider_id="whispermlx",
            model="large-v3",
            language="en",
            diarize=False,
            timeout_seconds=1,
        )
        result = provider.transcribe(audio, out_dir, options)
        proc.kill.assert_called_once()
        assert not result.success

    @patch("transcriptx.services.transcription.whispermlx_provider.subprocess.Popen")
    @patch(
        "transcriptx.services.transcription.whispermlx_provider.resolve_whispermlx_binary",
        return_value=Path("/usr/bin/whispermlx"),
    )
    def test_non_zero_return_gives_failed_result(
        self, _mock_binary, mock_popen, tmp_path: Path
    ):
        audio = tmp_path / "clip.mp3"
        audio.write_bytes(b"x")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        proc = MagicMock()
        proc.communicate.return_value = ("", "boom")
        proc.returncode = 2
        mock_popen.return_value = proc

        provider = WhisperMLXProvider()
        options = TranscriptionOptions(
            provider_id="whispermlx",
            model="large-v3",
            language="en",
            diarize=False,
        )
        result = provider.transcribe(audio, out_dir, options)
        assert not result.success
        assert result.returncode == 2


@pytest.mark.unit
def test_json_discovery_prefers_exact_stem(tmp_path: Path):
    out = tmp_path / "out"
    out.mkdir()
    exact = out / "clip.json"
    exact.write_text(json.dumps({"segments": []}), encoding="utf-8")
    other = out / "other.json"
    other.write_text("{}", encoding="utf-8")
    found = _discover_json(out, "clip", started_at=0.0)
    assert found == exact


@pytest.mark.unit
def test_json_discovery_newest_since_started_at(tmp_path: Path, monkeypatch):
    import time

    out = tmp_path / "out"
    out.mkdir()
    old = out / "old.json"
    old.write_text("{}", encoding="utf-8")
    started = time.time()
    new = out / "new.json"
    new.write_text("{}", encoding="utf-8")
    found = _discover_json(out, "missing", started_at=started)
    assert found == new


@pytest.mark.unit
@patch("transcriptx.services.transcription.whispermlx_provider.subprocess.Popen")
@patch(
    "transcriptx.services.transcription.whispermlx_provider.resolve_whispermlx_binary",
    return_value=Path("/usr/bin/whispermlx"),
)
@patch(
    "transcriptx.services.transcription.whispermlx_provider.get_secret",
    return_value="hf_secret_token",
)
def test_hf_token_passed_via_subprocess_env_not_argv(
    _mock_secret, _mock_binary, mock_popen, tmp_path: Path
):
    audio = tmp_path / "clip.mp3"
    audio.write_bytes(b"x")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "clip.json").write_text("{}", encoding="utf-8")
    proc = MagicMock()
    proc.communicate.return_value = ("", "")
    proc.returncode = 0
    mock_popen.return_value = proc

    provider = WhisperMLXProvider()
    options = TranscriptionOptions(
        provider_id="whispermlx",
        model="large-v3",
        language="en",
        diarize=True,
    )
    provider.transcribe(audio, out_dir, options)
    cmd = mock_popen.call_args[0][0]
    env = mock_popen.call_args[1]["env"]
    assert "hf_secret_token" not in cmd
    assert env["HF_TOKEN"] == "hf_secret_token"
