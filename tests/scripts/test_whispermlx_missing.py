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

    def test_disambiguated_archive_name_matches(self, wm, tmp_path: Path):
        (tmp_path / "foo (1).json").write_text("{}", encoding="utf-8")
        found = wm.find_existing_transcript(tmp_path, "foo")
        assert found is not None
        assert found.name == "foo (1).json"

    def test_disambiguated_non_numeric_does_not_match(self, wm, tmp_path: Path):
        (tmp_path / "foo (notes).json").write_text("{}", encoding="utf-8")
        assert wm.find_existing_transcript(tmp_path, "foo") is None

    def test_case_insensitive_exact_name(self, wm, tmp_path: Path):
        (tmp_path / "Foo.json").write_text("{}", encoding="utf-8")
        found = wm.find_existing_transcript(tmp_path, "foo")
        assert found is not None
        assert found.name.lower() == "foo.json"


@pytest.mark.unit
class TestSkipSearchDirs:
    def test_originals_includes_parent_library_and_source(self, wm, tmp_path: Path):
        library = tmp_path / "transcripts"
        originals = library / "originals"
        source = tmp_path / "recordings"
        originals.mkdir(parents=True)
        source.mkdir()
        dirs = wm.skip_search_dirs(originals, source=source)
        assert dirs == [originals, library, source]

    def test_non_originals_does_not_include_parent(self, wm, tmp_path: Path):
        out = tmp_path / "engine-out"
        source = tmp_path / "recordings"
        out.mkdir()
        source.mkdir()
        (out.parent / "unrelated.json").write_text("{}", encoding="utf-8")
        dirs = wm.skip_search_dirs(out, source=source)
        assert dirs == [out, source]
        assert wm.find_existing_transcript_in_dirs(dirs, "unrelated") is None

    def test_library_root_json_counts_as_done(self, wm, tmp_path: Path):
        library = tmp_path / "transcripts"
        originals = library / "originals"
        originals.mkdir(parents=True)
        (library / "clip.json").write_text("{}", encoding="utf-8")
        found = wm.find_existing_transcript_in_dirs(
            wm.skip_search_dirs(originals), "clip"
        )
        assert found == library / "clip.json"

    def test_source_sidecar_counts_as_done(self, wm, tmp_path: Path):
        originals = tmp_path / "originals"
        source = tmp_path / "recordings"
        originals.mkdir()
        source.mkdir()
        (source / "clip.json").write_text("{}", encoding="utf-8")
        found = wm.find_existing_transcript_in_dirs(
            wm.skip_search_dirs(originals, source=source), "clip"
        )
        assert found == source / "clip.json"


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
        cfg = wm.resolve_config(args, config_path=config_path)
        assert str(cfg.source) == "/from/cli"
        assert str(cfg.transcripts) == "/transcripts/file"
        assert cfg.model == "large-v3"
        assert cfg.language == "en"
        assert cfg.provenance.source == "cli"
        assert cfg.provenance.transcripts == "json"


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

    def test_dry_run_skips_library_root_json(
        self, wm, tmp_path: Path, monkeypatch, capsys
    ):
        source = tmp_path / "recordings"
        library = tmp_path / "transcripts"
        originals = library / "originals"
        source.mkdir()
        originals.mkdir(parents=True)
        (source / "clip.mp3").write_bytes(b"x")
        (library / "clip.json").write_text("{}", encoding="utf-8")

        fake_bin = tmp_path / "whispermlx"
        fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
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
                    str(originals),
                    "--whispermlx",
                    str(fake_bin),
                    "--no-diarize",
                    "--dry-run",
                ]
            )

        mock_run.assert_not_called()
        assert rc == 0
        out = capsys.readouterr().out
        assert "would process: 0" in out
        assert "skipped:   1" in out
        assert "clip.mp3" not in out


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
        assert "skipped:   12" in out
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


@pytest.mark.unit
class TestPortableConfig:
    def test_portable_defaults_do_not_trigger_processing(self, wm, monkeypatch):
        monkeypatch.setattr(wm, "CONFIG_PATH", Path("/nonexistent/config.json"))
        monkeypatch.delenv("TRANSCRIPTX_RECORDINGS_DIR", raising=False)
        monkeypatch.delenv("TRANSCRIPTX_TRANSCRIPTS_DIR", raising=False)
        cfg = wm.resolve_config(wm.parse_args([]))
        assert cfg.provenance.source == "portable"
        assert cfg.provenance.transcripts == "portable"
        assert not wm._processing_will_run(wm.parse_args([]), cfg)

    def test_env_transcripts_appends_originals(self, wm, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "missing.json")
        base = tmp_path / "transcripts-base"
        monkeypatch.setenv("TRANSCRIPTX_TRANSCRIPTS_DIR", str(base))
        monkeypatch.delenv("TRANSCRIPTX_RECORDINGS_DIR", raising=False)
        cfg = wm.resolve_config(wm.parse_args([]))
        assert cfg.transcripts == base / "originals"
        assert cfg.provenance.transcripts == "env"

    def test_json_transcripts_used_exactly(self, wm, tmp_path: Path, monkeypatch):
        config_path = tmp_path / "config.json"
        exact = tmp_path / "custom-output"
        config_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "source": "/audio",
                    "transcripts": str(exact),
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(wm, "CONFIG_PATH", config_path)
        cfg = wm.resolve_config(wm.parse_args([]))
        assert cfg.transcripts == exact
        assert cfg.provenance.transcripts == "json"

    def test_cli_transcripts_used_exactly(self, wm, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "missing.json")
        exact = tmp_path / "cli-output"
        cfg = wm.resolve_config(
            wm.parse_args(["--source", "/audio", "--transcripts", str(exact)])
        )
        assert cfg.transcripts == exact
        assert cfg.provenance.transcripts == "cli"

    def test_custom_config_path_outside_transcriptx(
        self, wm, tmp_path: Path, monkeypatch
    ):
        custom = tmp_path / "standalone.json"
        custom.write_text(
            json.dumps(
                {
                    "version": 1,
                    "source": "/standalone/audio",
                    "transcripts": "/standalone/out",
                    "env_file": "/standalone/whisperx.env",
                    "whispermlx": "/standalone/whispermlx",
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(wm, "find_repo_root", lambda: None)
        args = wm.parse_args(["--config", str(custom)])
        assert wm.resolve_config_path(args) == custom
        cfg = wm.resolve_config(args, config_path=custom)
        assert str(cfg.source) == "/standalone/audio"
        assert cfg.provenance.source == "json"

    def test_whispermlx_missing_config_env_overrides_default(
        self, wm, tmp_path: Path, monkeypatch
    ):
        custom = tmp_path / "from-env.json"
        monkeypatch.setenv(wm.CONFIG_ENV_VAR, str(custom))
        monkeypatch.setattr(wm, "find_repo_root", lambda: None)
        args = wm.parse_args([])
        assert wm.resolve_config_path(args) == custom

    def test_env_paths_trigger_processing(self, wm, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "missing.json")
        monkeypatch.setenv("TRANSCRIPTX_RECORDINGS_DIR", str(tmp_path / "rec"))
        monkeypatch.setenv("TRANSCRIPTX_TRANSCRIPTS_DIR", str(tmp_path / "tx"))
        cfg = wm.resolve_config(wm.parse_args([]))
        assert wm._processing_will_run(wm.parse_args([]), cfg)

    def test_save_config_alone_no_subprocess(self, wm, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "cfg.json")
        with patch.object(wm.subprocess, "run") as mock_run:
            rc = wm.main(["--save-config"])
        mock_run.assert_not_called()
        assert rc == 0


@pytest.mark.unit
class TestSkipSerial:
    def _write_mp3s(self, folder: Path, names: tuple[str, ...]) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        for name in names:
            (folder / name).write_bytes(b"x")

    def _dry_run_argv(
        self,
        tmp_path: Path,
        source: Path,
        transcripts: Path,
        extra: list[str],
    ) -> list[str]:
        fake_bin = tmp_path / "whispermlx"
        if not fake_bin.exists():
            fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_bin.chmod(0o755)
        argv = [
            "--source",
            str(source),
            "--transcripts",
            str(transcripts),
            "--whispermlx",
            str(fake_bin),
            "--no-diarize",
            "--dry-run",
        ]
        argv.extend(extra)
        return argv

    def test_off_by_default_would_process_parts(
        self, wm, tmp_path: Path, monkeypatch, capsys
    ):
        source = tmp_path / "audio"
        transcripts = tmp_path / "tx"
        self._write_mp3s(
            source, ("meeting_part1.mp3", "meeting_part2.mp3", "standalone.mp3")
        )
        transcripts.mkdir()
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "noconfig.json")
        with (
            patch.object(wm, "probe_output_format_support", return_value=True),
            patch.object(wm.subprocess, "run"),
        ):
            rc = wm.main(self._dry_run_argv(tmp_path, source, transcripts, []))
        out = capsys.readouterr().out
        assert rc == 0
        assert "would process: 3" in out
        assert "skipped likely serial" not in out

    def test_skip_serial_leaves_parts_and_runs_standalone(
        self, wm, tmp_path: Path, monkeypatch, capsys
    ):
        source = tmp_path / "audio"
        transcripts = tmp_path / "tx"
        self._write_mp3s(
            source, ("meeting_part1.mp3", "meeting_part2.mp3", "standalone.mp3")
        )
        transcripts.mkdir()
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "noconfig.json")
        with (
            patch.object(wm, "probe_output_format_support", return_value=True),
            patch.object(wm.subprocess, "run"),
        ):
            rc = wm.main(
                self._dry_run_argv(tmp_path, source, transcripts, ["--skip-serial"])
            )
        captured = capsys.readouterr()
        text = captured.out + captured.err
        assert rc == 0
        assert "would process: 1" in text
        assert "standalone.mp3" in text
        assert "skipped likely serial: 2" in text
        assert "meeting_part1.mp3" in text
        assert "meeting_part2.mp3" in text
        assert "likely serial, merge later" in text

    def test_skip_serial_whatsapp_burst(
        self, wm, tmp_path: Path, monkeypatch, capsys
    ):
        source = tmp_path / "audio"
        transcripts = tmp_path / "tx"
        self._write_mp3s(
            source,
            (
                "WhatsApp Audio 2026-08-12 at 13.11.09.mp3",
                "WhatsApp Audio 2026-08-12 at 13.12.05.mp3",
                "interview.mp3",
            ),
        )
        transcripts.mkdir()
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "noconfig.json")
        with (
            patch.object(wm, "probe_output_format_support", return_value=True),
            patch.object(wm.subprocess, "run"),
        ):
            rc = wm.main(
                self._dry_run_argv(tmp_path, source, transcripts, ["--skip-serial"])
            )
        text = capsys.readouterr().out
        assert rc == 0
        assert "would process: 1" in text
        assert "interview.mp3" in text
        assert "skipped likely serial: 2" in text

    def test_merged_output_still_processed(
        self, wm, tmp_path: Path, monkeypatch, capsys
    ):
        source = tmp_path / "audio"
        transcripts = tmp_path / "tx"
        self._write_mp3s(
            source,
            ("meeting_part1.mp3", "meeting_part2.mp3", "meeting_merged.mp3"),
        )
        transcripts.mkdir()
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "noconfig.json")
        with (
            patch.object(wm, "probe_output_format_support", return_value=True),
            patch.object(wm.subprocess, "run"),
        ):
            rc = wm.main(
                self._dry_run_argv(tmp_path, source, transcripts, ["--skip-serial"])
            )
        text = capsys.readouterr().out
        assert rc == 0
        assert "would process: 1" in text
        assert "meeting_merged.mp3" in text

    def test_json_config_enables_skip_serial(
        self, wm, tmp_path: Path, monkeypatch, capsys
    ):
        source = tmp_path / "audio"
        transcripts = tmp_path / "tx"
        self._write_mp3s(source, ("talk_part1.mp3", "talk_part2.mp3"))
        transcripts.mkdir()
        config_path = tmp_path / "cfg.json"
        config_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "source": str(source),
                    "transcripts": str(transcripts),
                    "skip_serial": True,
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(wm, "CONFIG_PATH", config_path)
        fake_bin = tmp_path / "whispermlx"
        fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake_bin.chmod(0o755)
        with (
            patch.object(wm, "probe_output_format_support", return_value=True),
            patch.object(wm.subprocess, "run"),
        ):
            rc = wm.main(
                ["--whispermlx", str(fake_bin), "--no-diarize", "--dry-run"]
            )
        text = capsys.readouterr().out
        assert rc == 0
        assert "would process: 0" in text
        assert "skipped likely serial: 2" in text

    def test_no_skip_serial_overrides_config(
        self, wm, tmp_path: Path, monkeypatch, capsys
    ):
        source = tmp_path / "audio"
        transcripts = tmp_path / "tx"
        self._write_mp3s(source, ("talk_part1.mp3", "talk_part2.mp3"))
        transcripts.mkdir()
        config_path = tmp_path / "cfg.json"
        config_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "source": str(source),
                    "transcripts": str(transcripts),
                    "skip_serial": True,
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(wm, "CONFIG_PATH", config_path)
        fake_bin = tmp_path / "whispermlx"
        fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake_bin.chmod(0o755)
        with (
            patch.object(wm, "probe_output_format_support", return_value=True),
            patch.object(wm.subprocess, "run"),
        ):
            rc = wm.main(
                [
                    "--whispermlx",
                    str(fake_bin),
                    "--no-diarize",
                    "--no-skip-serial",
                    "--dry-run",
                ]
            )
        text = capsys.readouterr().out
        assert rc == 0
        assert "would process: 2" in text

    def test_lite_fallback_when_transcriptx_unavailable(
        self, wm, tmp_path: Path, monkeypatch, capsys
    ):
        monkeypatch.setattr(wm, "detect_serial_groups_via_transcriptx", lambda _p: None)
        source = tmp_path / "audio"
        transcripts = tmp_path / "tx"
        self._write_mp3s(
            source, ("meeting_part1.mp3", "meeting_part2.mp3", "standalone.mp3")
        )
        transcripts.mkdir()
        monkeypatch.setattr(wm, "CONFIG_PATH", tmp_path / "noconfig.json")
        with (
            patch.object(wm, "probe_output_format_support", return_value=True),
            patch.object(wm.subprocess, "run"),
        ):
            rc = wm.main(
                self._dry_run_argv(tmp_path, source, transcripts, ["--skip-serial"])
            )
        captured = capsys.readouterr()
        text = captured.out + captured.err
        assert rc == 0
        assert "lite detector" in text
        assert "would process: 1" in text
        assert "skipped likely serial: 2" in text


@pytest.mark.unit
class TestNoPersonalPathsInTouchedFiles:
    _FILES = (
        Path("scripts/whispermlx-missing.py"),
        Path("config/whispermlx-missing.example.json"),
        Path("docs/runtime/transcription.md"),
        Path("src/transcriptx/web/page_modules/transcribe_audio.py"),
    )

    def test_no_machine_specific_paths(self):
        repo = Path(__file__).resolve().parent.parent.parent
        needle = "/Users/89298"
        for rel in self._FILES:
            text = (repo / rel).read_text(encoding="utf-8")
            assert needle not in text, f"{rel} contains personal path"
