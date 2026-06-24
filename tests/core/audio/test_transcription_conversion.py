"""Tests for export_mp3_for_transcription."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.audio.conversion import export_mp3_for_transcription


@pytest.mark.unit
class TestExportMp3ForTranscription:
    def test_mp3_skip_returns_original_path(self, tmp_path: Path):
        mp3 = tmp_path / "clip.mp3"
        mp3.write_bytes(b"fake")
        out = tmp_path / "staged.mp3"
        result = export_mp3_for_transcription(mp3, out, force_reencode=False)
        assert result.resolve() == mp3.resolve()
        assert not out.exists()

    @patch("transcriptx.core.audio.conversion.check_ffmpeg_available", return_value=(True, None))
    @patch("transcriptx.core.audio.conversion._find_ffmpeg_path", return_value="/usr/bin/ffmpeg")
    @patch("transcriptx.core.audio.conversion.subprocess.run")
    def test_wav_builds_expected_ffmpeg_command(
        self, mock_run, _mock_path, _mock_ff, tmp_path: Path
    ):
        wav = tmp_path / "clip.wav"
        wav.write_bytes(b"fake")
        out = tmp_path / "clip.mp3"
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        export_mp3_for_transcription(
            wav,
            out,
            codec="libmp3lame",
            bitrate="128k",
            channels=2,
            sample_rate=0,
        )

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "/usr/bin/ffmpeg"
        assert "-codec:a" in cmd and "libmp3lame" in cmd
        assert "-b:a" in cmd and "128k" in cmd
        assert "-ac" in cmd and "2" in cmd
        assert "-ar" not in cmd

    @patch("transcriptx.core.audio.conversion.check_ffmpeg_available", return_value=(True, None))
    @patch("transcriptx.core.audio.conversion._find_ffmpeg_path", return_value="/usr/bin/ffmpeg")
    @patch("transcriptx.core.audio.conversion.subprocess.run")
    def test_positive_sample_rate_includes_ar(
        self, mock_run, _mock_path, _mock_ff, tmp_path: Path
    ):
        wav = tmp_path / "clip.wav"
        wav.write_bytes(b"fake")
        out = tmp_path / "clip.mp3"
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        export_mp3_for_transcription(wav, out, sample_rate=16000)

        cmd = mock_run.call_args[0][0]
        assert "-ar" in cmd
        assert "16000" in cmd

    @patch("transcriptx.core.audio.conversion.check_ffmpeg_available", return_value=(True, None))
    @patch("transcriptx.core.audio.conversion._find_ffmpeg_path", return_value="/usr/bin/ffmpeg")
    @patch("transcriptx.core.audio.conversion.subprocess.run")
    def test_ffmpeg_failure_raises_clear_error(
        self, mock_run, _mock_path, _mock_ff, tmp_path: Path
    ):
        wav = tmp_path / "clip.wav"
        wav.write_bytes(b"fake")
        out = tmp_path / "clip.mp3"
        mock_run.return_value = MagicMock(returncode=1, stderr="codec failed\nline2")

        with pytest.raises(RuntimeError, match="ffmpeg failed"):
            export_mp3_for_transcription(wav, out)
