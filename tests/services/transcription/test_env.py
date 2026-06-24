"""Tests for transcription env loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.app.models.requests import TranscriptionOptions
from transcriptx.services.transcription import env as tx_env


@pytest.mark.unit
class TestEnvParsing:
    def test_parse_key_value(self, tmp_path: Path):
        env_file = tmp_path / "whisperx.env"
        env_file.write_text("WHISPERMLX_MODEL=large-v3\n", encoding="utf-8")
        parsed = tx_env.parse_env_file(env_file)
        assert parsed["WHISPERMLX_MODEL"] == "large-v3"

    def test_parse_export_key_value(self, tmp_path: Path):
        env_file = tmp_path / "whisperx.env"
        env_file.write_text("export HF_TOKEN=secret\n", encoding="utf-8")
        parsed = tx_env.parse_env_file(env_file)
        assert parsed["HF_TOKEN"] == "secret"

    def test_ignore_comments_and_blanks(self, tmp_path: Path):
        env_file = tmp_path / "whisperx.env"
        env_file.write_text(
            "# comment\n\nWHISPERMLX_LANGUAGE=en\n",
            encoding="utf-8",
        )
        parsed = tx_env.parse_env_file(env_file)
        assert parsed == {"WHISPERMLX_LANGUAGE": "en"}

    def test_parse_bool(self):
        assert tx_env.parse_bool("true") is True
        assert tx_env.parse_bool("false") is False
        assert tx_env.parse_bool(None, default=True) is True

    def test_parse_int(self):
        assert tx_env.parse_int("16000") == 16000
        assert tx_env.parse_int("", default=0) == 0

    def test_transcription_options_has_no_hf_token(self):
        opts = tx_env.default_transcription_options(
            {"WHISPERMLX_MODEL": "large-v3", "HF_TOKEN": "secret"}
        )
        assert isinstance(opts, TranscriptionOptions)
        assert not hasattr(opts, "hf_token")
        assert "HF_TOKEN" not in repr(opts)

    def test_keep_intermediates_maps_to_request_flags(self):
        flags = tx_env.default_request_flags({"TRANSCRIPTION_KEEP_INTERMEDIATES": "true"})
        assert flags["keep_intermediates"] is True

    def test_strip_simple_quotes(self, tmp_path: Path):
        env_file = tmp_path / "whisperx.env"
        env_file.write_text('WHISPERMLX="/opt/bin/whispermlx"\n', encoding="utf-8")
        parsed = tx_env.parse_env_file(env_file)
        assert parsed["WHISPERMLX"] == "/opt/bin/whispermlx"

    def test_merge_env_os_environ_overrides_file(self, tmp_path: Path, monkeypatch):
        env_file = tmp_path / "whisperx.env"
        env_file.write_text("WHISPERMLX_MODEL=from-file\n", encoding="utf-8")
        monkeypatch.setattr(tx_env, "find_whisperx_env_path", lambda: env_file)
        monkeypatch.setenv("WHISPERMLX_MODEL", "from-os")
        merged = tx_env.load_merged_env(overrides={"WHISPERMLX_MODEL": "from-ui"})
        assert merged["WHISPERMLX_MODEL"] == "from-ui"

    def test_get_secret_never_in_transcription_options(self):
        opts = tx_env.build_transcription_options(
            overrides={"model": "large-v3"},
            env={"HF_TOKEN": "hf_secret", "WHISPERMLX_MODEL": "large-v3"},
        )
        assert opts.model == "large-v3"
        assert "secret" not in repr(opts)
