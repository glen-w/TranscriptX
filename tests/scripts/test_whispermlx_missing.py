"""Tests for scripts/whispermlx-missing.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "whispermlx-missing.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("whispermlx_missing", _SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["whispermlx_missing"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def wm():
    return _load_module()


@pytest.mark.unit
class TestFindExistingTranscript:
    def test_exact_names_match(self, wm, tmp_path: Path):
        stem = "260709_Neptune_Forum_2"
        for suffix in wm._EXACT_SUFFIXES:
            (tmp_path / f"{stem}{suffix}").write_text("{}", encoding="utf-8")
            found = wm.find_existing_transcript(tmp_path, stem)
            assert found is not None
            assert found.name == f"{stem}{suffix}"
            (tmp_path / f"{stem}{suffix}").unlink()

    def test_unrelated_json_does_not_match(self, wm, tmp_path: Path):
        (tmp_path / "other.json").write_text("{}", encoding="utf-8")
        assert wm.find_existing_transcript(tmp_path, "foo") is None

    def test_fuzzy_does_not_match_foo2_for_foo(self, wm, tmp_path: Path):
        (tmp_path / "foo2.json").write_text("{}", encoding="utf-8")
        assert wm.find_existing_transcript(tmp_path, "foo", fuzzy=True) is None

    def test_fuzzy_positive_separators(self, wm, tmp_path: Path):
        for name in ("foo-extra.json", "foo_extra.json", "foo.extra.json"):
            (tmp_path / name).write_text("{}", encoding="utf-8")
            found = wm.find_existing_transcript(tmp_path, "foo", fuzzy=True)
            assert found is not None
            assert found.name == name
            (tmp_path / name).unlink()


@pytest.mark.unit
class TestDiscoverMp3s:
    def test_case_insensitive_and_spaces(self, wm, tmp_path: Path):
        (tmp_path / "a.mp3").write_bytes(b"x")
        (tmp_path / "B.MP3").write_bytes(b"x")
        (tmp_path / "my recording.mp3").write_bytes(b"x")
        (tmp_path / "not-audio.txt").write_text("nope", encoding="utf-8")

        found = wm.discover_mp3s(tmp_path)
        names = {p.name for p in found}
        assert names == {"a.mp3", "B.MP3", "my recording.mp3"}


@pytest.mark.unit
class TestParseEnvFile:
    def test_key_value_and_export_and_quotes(self, wm, tmp_path: Path):
        env = tmp_path / "test.env"
        env.write_text(
            "\n".join(
                [
                    "# comment",
                    "PLAIN=value",
                    "export QUOTED='hello world'",
                    'DOUBLE="x"',
                ]
            ),
            encoding="utf-8",
        )
        parsed = wm.parse_env_file(env)
        assert parsed["PLAIN"] == "value"
        assert parsed["QUOTED"] == "hello world"
        assert parsed["DOUBLE"] == "x"


@pytest.mark.unit
class TestConfigPath:
    def test_cli_config_overrides_default(self, wm, tmp_path: Path, monkeypatch):
        monkeypatch.delenv(wm.CONFIG_ENV_VAR, raising=False)
        custom = tmp_path / "my-config.json"
        args = wm.parse_args(["--config", str(custom)])
        assert wm.resolve_config_path(args) == custom

    def test_env_config_overrides_default(self, wm, tmp_path: Path, monkeypatch):
        custom = tmp_path / "env-config.json"
        monkeypatch.setenv(wm.CONFIG_ENV_VAR, str(custom))
        args = wm.parse_args([])
        assert wm.resolve_config_path(args) == custom

    def test_cli_config_overrides_env(self, wm, tmp_path: Path, monkeypatch):
        monkeypatch.setenv(wm.CONFIG_ENV_VAR, str(tmp_path / "env.json"))
        cli_path = tmp_path / "cli.json"
        args = wm.parse_args(["--config", str(cli_path)])
        assert wm.resolve_config_path(args) == cli_path


@pytest.mark.unit
class TestResolveConfig:
    def test_precedence_defaults_file_cli(self, wm, tmp_path: Path, monkeypatch):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_path = config_dir / "config.json"
        monkeypatch.setattr(wm, "CONFIG_PATH", config_path)

        config_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "source": "/from/file",
                    "transcripts": "/transcripts/file",
                    "model": "medium",
                }
            ),
            encoding="utf-8",
        )

        args = wm.parse_args(["--source", "/from/cli", "--model", "large-v3"])
        cfg = wm.resolve_config(args)
        assert str(cfg.source) == "/from/cli"
        assert str(cfg.transcripts) == "/transcripts/file"
        assert cfg.model == "large-v3"
        assert cfg.language == "en"


@pytest.mark.unit
class TestValidateJsonFile:
    def test_rejects_empty_and_invalid(self, wm, tmp_path: Path):
        empty = tmp_path / "empty.json"
        empty.write_text("   ", encoding="utf-8")
        ok, reason = wm.validate_json_file(empty)
        assert not ok
        assert "empty" in reason.lower()

        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        ok, reason = wm.validate_json_file(bad)
        assert not ok
        assert "invalid" in reason.lower()

    def test_accepts_valid_json(self, wm, tmp_path: Path):
        good = tmp_path / "good.json"
        good.write_text('{"segments": []}', encoding="utf-8")
        ok, reason = wm.validate_json_file(good)
        assert ok
        assert reason == ""


@pytest.mark.unit
class TestDryRun:
    def test_dry_run_does_not_call_subprocess(self, wm, tmp_path: Path, monkeypatch):
        source = tmp_path / "audio"
        transcripts = tmp_path / "transcripts"
        source.mkdir()
        transcripts.mkdir()
        env_file = tmp_path / "whisperx.env"
        env_file.write_text("HF_TOKEN=hf_test_token\n", encoding="utf-8")
        fake_bin = tmp_path / "whispermlx"
        fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake_bin.chmod(0o755)

        (source / "clip.mp3").write_bytes(b"x")

        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "noconfig.json")

        with (
            patch.object(wm, "probe_output_format_support", return_value=True),
            patch.object(wm.subprocess, "run") as mock_run,
        ):
            rc = wm.main(
                [
                    "--source",
                    str(source),
                    "--transcripts",
                    str(transcripts),
                    "--env-file",
                    str(env_file),
                    "--whispermlx",
                    str(fake_bin),
                    "--no-diarize",
                    "--dry-run",
                ]
            )

        mock_run.assert_not_called()
        assert rc == 0


@pytest.mark.unit
class TestProcessOnePromotion:
    def _cfg(self, wm, tmp_path: Path, source: Path, transcripts: Path):
        return wm.EffectiveConfig(
            source=source,
            transcripts=transcripts,
            env_file=tmp_path / "env",
            whispermlx=tmp_path / "bin",
            model="large-v3",
            language="en",
            diarize=False,
            output_format="json",
            use_output_format_flag=False,
            clean_non_json=True,
            extra_whisper_args=[],
            pass_hf_token_arg=False,
            fuzzy_json_match=False,
            follow_output=True,
        )

    def test_invalid_json_not_promoted(self, wm, tmp_path: Path):
        source = tmp_path / "audio"
        transcripts = tmp_path / "transcripts"
        source.mkdir()
        transcripts.mkdir()
        mp3 = source / "clip.mp3"
        mp3.write_bytes(b"x")

        cfg = self._cfg(wm, tmp_path, source, transcripts)

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = ""
        proc.stderr = ""

        with patch.object(wm.subprocess, "run", return_value=proc):
            outcome, failed = wm.process_one(
                cfg,
                mp3,
                force=False,
                proc_env={},
                hf_token=None,
                output_format_supported=False,
                keep_temp=True,
                clean_failed=False,
                dry_run=False,
                quiet=True,
            )

        assert outcome == "failed"
        assert failed is not None
        assert not (transcripts / "clip.json").exists()

    def test_force_replaces_only_after_valid_json(self, wm, tmp_path: Path):
        source = tmp_path / "audio"
        transcripts = tmp_path / "transcripts"
        source.mkdir()
        transcripts.mkdir()
        mp3 = source / "clip.mp3"
        mp3.write_bytes(b"x")

        target = transcripts / "clip.json"
        target.write_text('{"old": true}', encoding="utf-8")

        cfg = self._cfg(wm, tmp_path, source, transcripts)

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = ""
        proc.stderr = ""

        def _run_side_effect(cmd, **kwargs):
            out_idx = cmd.index("--output_dir") + 1
            temp_dir = Path(cmd[out_idx])
            (temp_dir / "clip.json").write_text('{"segments": []}', encoding="utf-8")
            return proc

        with patch.object(wm.subprocess, "run", side_effect=_run_side_effect):
            outcome, failed = wm.process_one(
                cfg,
                mp3,
                force=True,
                proc_env={},
                hf_token=None,
                output_format_supported=False,
                keep_temp=False,
                clean_failed=False,
                dry_run=False,
                quiet=True,
            )

        assert outcome == "processed"
        assert failed is None
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data == {"segments": []}

    def test_force_does_not_replace_on_invalid_json(self, wm, tmp_path: Path):
        source = tmp_path / "audio"
        transcripts = tmp_path / "transcripts"
        source.mkdir()
        transcripts.mkdir()
        mp3 = source / "clip.mp3"
        mp3.write_bytes(b"x")

        target = transcripts / "clip.json"
        target.write_text('{"old": true}', encoding="utf-8")

        cfg = self._cfg(wm, tmp_path, source, transcripts)

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = ""
        proc.stderr = ""

        def _run_side_effect(cmd, **kwargs):
            out_idx = cmd.index("--output_dir") + 1
            temp_dir = Path(cmd[out_idx])
            (temp_dir / "clip.json").write_text("not-json", encoding="utf-8")
            return proc

        with patch.object(wm.subprocess, "run", side_effect=_run_side_effect):
            outcome, failed = wm.process_one(
                cfg,
                mp3,
                force=True,
                proc_env={},
                hf_token=None,
                output_format_supported=False,
                keep_temp=True,
                clean_failed=False,
                dry_run=False,
                quiet=True,
            )

        assert outcome == "failed"
        assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}


@pytest.mark.unit
class TestFollowOutput:
    def _cfg(self, wm, tmp_path: Path, source: Path, transcripts: Path):
        return wm.EffectiveConfig(
            source=source,
            transcripts=transcripts,
            env_file=tmp_path / "env",
            whispermlx=tmp_path / "bin",
            model="large-v3",
            language="en",
            diarize=False,
            output_format="json",
            use_output_format_flag=False,
            clean_non_json=True,
            extra_whisper_args=[],
            pass_hf_token_arg=False,
            fuzzy_json_match=False,
            follow_output=True,
        )

    def test_follow_output_streams_by_default(self, wm, tmp_path: Path):
        source = tmp_path / "audio"
        transcripts = tmp_path / "transcripts"
        source.mkdir()
        transcripts.mkdir()
        mp3 = source / "clip.mp3"
        mp3.write_bytes(b"x")
        cfg = self._cfg(wm, tmp_path, source, transcripts)

        proc = MagicMock()
        proc.returncode = 0

        def _run_side_effect(cmd, **kwargs):
            out_idx = cmd.index("--output_dir") + 1
            temp_dir = Path(cmd[out_idx])
            (temp_dir / "clip.json").write_text('{"segments": []}', encoding="utf-8")
            return proc

        with patch.object(
            wm.subprocess, "run", side_effect=_run_side_effect
        ) as mock_run:
            wm.process_one(
                cfg,
                mp3,
                force=False,
                proc_env={},
                hf_token=None,
                output_format_supported=False,
                keep_temp=False,
                clean_failed=False,
                dry_run=False,
                quiet=False,
            )
        assert "capture_output" not in mock_run.call_args.kwargs
        assert "text" not in mock_run.call_args.kwargs

    def test_quiet_captures_output(self, wm, tmp_path: Path):
        source = tmp_path / "audio"
        transcripts = tmp_path / "transcripts"
        source.mkdir()
        transcripts.mkdir()
        mp3 = source / "clip.mp3"
        mp3.write_bytes(b"x")
        cfg = self._cfg(wm, tmp_path, source, transcripts)

        proc = MagicMock()
        proc.returncode = 0
        proc.stderr = ""

        def _run_side_effect(cmd, **kwargs):
            out_idx = cmd.index("--output_dir") + 1
            temp_dir = Path(cmd[out_idx])
            (temp_dir / "clip.json").write_text('{"segments": []}', encoding="utf-8")
            return proc

        with patch.object(
            wm.subprocess, "run", side_effect=_run_side_effect
        ) as mock_run:
            wm.process_one(
                cfg,
                mp3,
                force=False,
                proc_env={},
                hf_token=None,
                output_format_supported=False,
                keep_temp=False,
                clean_failed=False,
                dry_run=False,
                quiet=True,
            )
        assert mock_run.call_args.kwargs.get("capture_output") is True

    def test_quiet_failure_prints_stderr_tail(self, wm, tmp_path: Path, capsys):
        source = tmp_path / "audio"
        transcripts = tmp_path / "transcripts"
        source.mkdir()
        transcripts.mkdir()
        mp3 = source / "clip.mp3"
        mp3.write_bytes(b"x")
        cfg = self._cfg(wm, tmp_path, source, transcripts)

        proc = MagicMock()
        proc.returncode = 1
        proc.stderr = "boom whispermlx failed"

        with patch.object(wm.subprocess, "run", return_value=proc):
            outcome, _ = wm.process_one(
                cfg,
                mp3,
                force=False,
                proc_env={},
                hf_token=None,
                output_format_supported=False,
                keep_temp=True,
                clean_failed=False,
                dry_run=False,
                quiet=True,
            )

        assert outcome == "failed"
        assert "boom whispermlx failed" in capsys.readouterr().err

    def test_resolve_config_quiet_flag(self, wm, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "missing.json")
        assert wm.resolve_config(wm.parse_args([])).follow_output is True
        assert wm.resolve_config(wm.parse_args(["--quiet"])).follow_output is False


@pytest.mark.unit
class TestShowConfig:
    def test_show_config_no_validation(self, wm, tmp_path: Path, monkeypatch, capsys):
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "missing.json")
        rc = wm.main(["--show-config"])
        assert rc == 0
        captured = capsys.readouterr()
        assert '"model": "large-v3"' in captured.out
        assert "probe not run" in captured.err.lower()


@pytest.mark.unit
class TestConfigTypeValidation:
    def test_require_bool_rejects_string_false_as_true(
        self, wm, tmp_path: Path, monkeypatch
    ):
        config_path = tmp_path / "config.json"
        monkeypatch.setattr(wm, "CONFIG_PATH", config_path)
        config_path.write_text(
            json.dumps({"version": 1, "diarize": "false"}),
            encoding="utf-8",
        )
        cfg = wm.resolve_config(wm.parse_args([]))
        assert cfg.diarize is False

    def test_require_bool_string_true(self, wm, tmp_path: Path, monkeypatch):
        config_path = tmp_path / "config.json"
        monkeypatch.setattr(wm, "CONFIG_PATH", config_path)
        config_path.write_text(
            json.dumps({"version": 1, "diarize": "true"}),
            encoding="utf-8",
        )
        cfg = wm.resolve_config(wm.parse_args([]))
        assert cfg.diarize is True


@pytest.mark.unit
class TestDiscoverJsonCandidate:
    def test_finds_nested_json(self, wm, tmp_path: Path):
        nested = tmp_path / "out" / "nested"
        nested.mkdir(parents=True)
        target = nested / "clip.json"
        target.write_text('{"segments": []}', encoding="utf-8")
        run_start = target.stat().st_mtime
        found = wm.discover_json_candidate(tmp_path, "clip", run_start)
        assert found == target


@pytest.mark.unit
class TestDryRunLightweight:
    def test_dry_run_without_env_or_hf_token(
        self, wm, tmp_path: Path, monkeypatch, capsys
    ):
        source = tmp_path / "audio"
        transcripts = tmp_path / "transcripts"
        source.mkdir()
        (source / "clip.mp3").write_bytes(b"x")
        fake_bin = tmp_path / "whispermlx"
        fake_bin.write_text("#!/bin/sh\n", encoding="utf-8")
        fake_bin.chmod(0o755)

        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "noconfig.json")

        with (
            patch.object(wm, "probe_output_format_support", return_value=True),
            patch.object(wm.subprocess, "run") as mock_run,
        ):
            rc = wm.main(
                [
                    "--source",
                    str(source),
                    "--transcripts",
                    str(transcripts),
                    "--env-file",
                    str(tmp_path / "missing.env"),
                    "--whispermlx",
                    str(fake_bin),
                    "--dry-run",
                ]
            )

        mock_run.assert_not_called()
        assert rc == 0
        out = capsys.readouterr().out
        assert "would process: 1" in out


@pytest.mark.unit
class TestDryRunSummaryLists:
    def test_summary_lists_first_ten_matches(
        self, wm, tmp_path: Path, monkeypatch, capsys
    ):
        source = tmp_path / "audio"
        transcripts = tmp_path / "transcripts"
        source.mkdir()
        transcripts.mkdir()

        for i in range(12):
            (source / f"new_{i:02d}.mp3").write_bytes(b"x")
        for i in range(12):
            (source / f"done_{i:02d}.mp3").write_bytes(b"x")
            (transcripts / f"done_{i:02d}.json").write_text("{}", encoding="utf-8")

        fake_bin = tmp_path / "whispermlx"
        fake_bin.write_text("#!/bin/sh\n", encoding="utf-8")
        fake_bin.chmod(0o755)
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "noconfig.json")

        with patch.object(wm, "probe_output_format_support", return_value=False):
            rc = wm.main(
                [
                    "--source",
                    str(source),
                    "--transcripts",
                    str(transcripts),
                    "--whispermlx",
                    str(fake_bin),
                    "--no-diarize",
                    "--dry-run",
                ]
            )

        assert rc == 0
        out = capsys.readouterr().out
        assert "would process: 12" in out
        assert "would process (first 10 of 12):" in out
        assert "new_00.mp3" in out
        assert "... and 2 more" in out
        assert "new_11.mp3" not in out
        assert "skipped" not in out
        assert "JSON match" not in out
        assert "done_00.mp3" not in out


@pytest.mark.unit
class TestSaveConfigBehaviour:
    def test_save_config_alone_exits_without_processing(
        self, wm, tmp_path: Path, monkeypatch, capsys
    ):
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "cfg.json")
        with patch.object(wm, "validate_for_processing") as mock_val:
            rc = wm.main(["--save-config"])
        mock_val.assert_not_called()
        assert rc == 0
        assert (tmp_path / "cfg.json").is_file()

    def test_save_config_with_paths_continues_to_processing(
        self, wm, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "cfg.json")
        source = tmp_path / "audio"
        transcripts = tmp_path / "transcripts"
        source.mkdir()
        transcripts.mkdir()
        env_file = tmp_path / "env"
        env_file.write_text("HF_TOKEN=token\n", encoding="utf-8")
        fake_bin = tmp_path / "whispermlx"
        fake_bin.write_text("#!/bin/sh\n", encoding="utf-8")
        fake_bin.chmod(0o755)

        with (
            patch.object(wm, "probe_output_format_support", return_value=True),
            patch.object(wm, "discover_mp3s", return_value=[]),
            patch.object(wm, "validate_for_processing") as mock_val,
        ):
            mock_val.return_value = ({}, "token")
            rc = wm.main(
                [
                    "--save-config",
                    "--source",
                    str(source),
                    "--transcripts",
                    str(transcripts),
                    "--env-file",
                    str(env_file),
                    "--whispermlx",
                    str(fake_bin),
                    "--no-diarize",
                ]
            )
        mock_val.assert_called_once()
        assert rc == 0
        assert (tmp_path / "cfg.json").is_file()


@pytest.mark.unit
class TestConfigErrors:
    def test_invalid_config_exits_2(self, wm, tmp_path: Path, monkeypatch):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(wm, "CONFIG_PATH", bad)
        rc = wm.main([])
        assert rc == 2


@pytest.mark.unit
class TestCleanFailedSummary:
    def test_clean_failed_omits_temp_path(self, wm, tmp_path: Path):
        source = tmp_path / "audio"
        transcripts = tmp_path / "transcripts"
        source.mkdir()
        transcripts.mkdir()
        mp3 = source / "clip.mp3"
        mp3.write_bytes(b"x")
        cfg = wm.EffectiveConfig(
            source=source,
            transcripts=transcripts,
            env_file=tmp_path / "env",
            whispermlx=tmp_path / "bin",
            model="large-v3",
            language="en",
            diarize=False,
            output_format="json",
            use_output_format_flag=False,
            clean_non_json=True,
            extra_whisper_args=[],
            pass_hf_token_arg=False,
            fuzzy_json_match=False,
            follow_output=True,
        )
        proc = MagicMock()
        proc.returncode = 1
        proc.stdout = ""
        proc.stderr = "fail"

        with patch.object(wm.subprocess, "run", return_value=proc):
            outcome, failed = wm.process_one(
                cfg,
                mp3,
                force=False,
                proc_env={},
                hf_token=None,
                output_format_supported=False,
                keep_temp=False,
                clean_failed=True,
                dry_run=False,
                quiet=True,
            )

        assert outcome == "failed"
        assert failed is not None
        assert failed.temp_dir is None
        assert "temp removed" in failed.reason
