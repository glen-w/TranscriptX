"""Tests for scripts/inbox-watch.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "inbox-watch.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("inbox_watch", _SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_watch"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def iw():
    return _load_module()


@pytest.fixture
def dirs(tmp_path: Path, iw):
    inbox = tmp_path / "inbox"
    recordings = tmp_path / "recordings"
    transcripts = tmp_path / "transcripts"
    inbox.mkdir()
    recordings.mkdir()
    transcripts.mkdir()
    iw.CONFIG_PATH = tmp_path / "noconfig.json"
    return inbox, recordings, transcripts


def _once_args(
    inbox: Path,
    recordings: Path,
    transcripts: Path,
    extra: list[str] | None = None,
) -> list[str]:
    args = [
        "--once",
        "--inbox",
        str(inbox),
        "--recordings",
        str(recordings),
        "--transcripts",
        str(transcripts),
        "--stability-checks",
        "1",
        "--ffmpeg",
        str(inbox.parent / "ffmpeg"),
        "--whispermlx-missing",
        str(inbox.parent / "whispermlx-missing.py"),
    ]
    if extra:
        args.extend(extra)
    return args


def _ok_ffmpeg(cmd):
    Path(cmd[-1]).write_bytes(b"mp3")
    return MagicMock(returncode=0, stderr="")


@pytest.mark.unit
class TestClassify:
    def test_audio_transcript_ignore(self, iw):
        assert iw.classify_path("a.m4a") == "audio"
        assert iw.classify_path("B.WAV") == "audio"
        assert iw.classify_path("talk.json") == "transcript"
        assert iw.classify_path("talk.srt") == "transcript"
        assert iw.classify_path("notes.txt") == "transcript"
        assert iw.classify_path("photo.jpg") == "ignore"
        assert iw.classify_path("readme.md") == "ignore"


@pytest.mark.unit
class TestFfmpegArgv:
    def test_canonical_flags(self, iw, tmp_path: Path):
        src = tmp_path / "clip.m4a"
        dest = tmp_path / "clip.mp3"
        cmd = iw.build_ffmpeg_cmd("/usr/bin/ffmpeg", src, dest)
        assert cmd[0] == "/usr/bin/ffmpeg"
        assert cmd[1:5] == ["-nostdin", "-y", "-i", str(src)]
        assert "-ac" in cmd and cmd[cmd.index("-ac") + 1] == "1"
        assert "-ar" in cmd and cmd[cmd.index("-ar") + 1] == "16000"
        assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "libmp3lame"
        assert "-b:a" in cmd and cmd[cmd.index("-b:a") + 1] == "64k"
        assert "-f" in cmd and cmd[cmd.index("-f") + 1] == "mp3"
        assert cmd[-1] == str(dest)

    def test_explicit_mp3_muxer_when_dest_is_partial(self, iw, tmp_path: Path):
        src = tmp_path / "clip.wav"
        dest = tmp_path / ".inbox-watch.clip.mp3.partial"
        cmd = iw.build_ffmpeg_cmd("/usr/bin/ffmpeg", src, dest)
        assert cmd[-3:] == ["-f", "mp3", str(dest)]


@pytest.mark.unit
class TestConvertProgress:
    def test_prints_converting_before_ffmpeg(self, iw, tmp_path, capsys, monkeypatch):
        recordings = tmp_path / "rec"
        recordings.mkdir()
        src = tmp_path / "clip.wav"
        src.write_bytes(b"x" * 2048)
        monkeypatch.setattr(iw, "run_ffmpeg", _ok_ffmpeg)
        monkeypatch.setattr(iw, "finalize_inbox_source", lambda *a, **k: None)
        cfg = MagicMock()
        stats = iw.CycleStats()
        outcome = iw.convert_audio(
            src,
            recordings,
            ffmpeg=Path("ffmpeg"),
            force=False,
            dry_run=False,
            cfg=cfg,
            stats=stats,
        )
        assert outcome == "converted"
        out = capsys.readouterr().out
        assert "Converting: clip.wav -> clip.mp3" in out
        assert "Converted: clip.wav -> clip.mp3" in out
        assert "in " in out and "s" in out


@pytest.mark.unit
class TestCycleFeedback:
    def test_review_and_summary_sections(self, iw, dirs, monkeypatch, capsys):
        inbox, recordings, transcripts = dirs
        (inbox / "clip.m4a").write_bytes(b"audio")
        monkeypatch.setattr(iw, "run_ffmpeg", _ok_ffmpeg)
        monkeypatch.setattr(iw, "run_whispermlx_missing", lambda _cmd: 0)
        rc = iw.main(
            _once_args(inbox, recordings, transcripts, ["--no-watch-transcripts"])
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Review before cycle" in out
        assert "Processing" in out
        assert "[1/1] audio: clip.m4a" in out
        assert "Run summary" in out
        assert "Status:   completed" in out
        assert "Converted" in out


@pytest.mark.unit
class TestStemMatch:
    def test_audio_stem_any_extension(self, iw, tmp_path: Path):
        rec = tmp_path / "rec"
        rec.mkdir()
        wav = rec / "foo.wav"
        wav.write_bytes(b"x")
        found = iw.find_stem_match(rec, "foo", iw.AUDIO_EXTENSIONS)
        assert found == wav
        assert iw.find_stem_match(rec, "bar", iw.AUDIO_EXTENSIONS) is None

    def test_transcript_stem_any_extension(self, iw, tmp_path: Path):
        dest = tmp_path / "tx"
        dest.mkdir()
        json_path = dest / "foo.json"
        json_path.write_text("{}", encoding="utf-8")
        found = iw.find_stem_match(dest, "foo", iw.TRANSCRIPT_EXTENSIONS)
        assert found == json_path
        srt = dest / "bar.srt"
        srt.write_text("1\n", encoding="utf-8")
        assert iw.find_stem_match(dest, "bar", iw.TRANSCRIPT_EXTENSIONS) == srt


@pytest.mark.unit
class TestPathGuards:
    def test_neither_mode(self, iw, dirs):
        inbox, recordings, transcripts = dirs
        rc = iw.main(
            _once_args(
                inbox,
                recordings,
                transcripts,
                ["--no-watch-audio", "--no-watch-transcripts"],
            )
        )
        assert rc == 2

    def test_inbox_under_recordings(self, iw, tmp_path: Path):
        recordings = tmp_path / "recordings"
        inbox = recordings / "drop"
        transcripts = tmp_path / "transcripts"
        recordings.mkdir()
        inbox.mkdir()
        transcripts.mkdir()
        iw.CONFIG_PATH = tmp_path / "noconfig.json"
        rc = iw.main(_once_args(inbox, recordings, transcripts))
        assert rc == 2

    def test_recordings_under_inbox(self, iw, tmp_path: Path):
        inbox = tmp_path / "inbox"
        recordings = inbox / "recordings"
        transcripts = tmp_path / "transcripts"
        inbox.mkdir()
        recordings.mkdir()
        transcripts.mkdir()
        iw.CONFIG_PATH = tmp_path / "noconfig.json"
        rc = iw.main(_once_args(inbox, recordings, transcripts))
        assert rc == 2


@pytest.mark.unit
class TestModeGating:
    def test_audio_only_ignores_transcripts(self, iw, dirs, monkeypatch):
        inbox, recordings, transcripts = dirs
        (inbox / "clip.m4a").write_bytes(b"audio")
        (inbox / "talk.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(iw, "run_ffmpeg", _ok_ffmpeg)
        monkeypatch.setattr(iw, "run_whispermlx_missing", lambda _cmd: 0)
        rc = iw.main(
            _once_args(inbox, recordings, transcripts, ["--no-watch-transcripts"])
        )
        assert rc == 0
        assert (recordings / "clip.mp3").is_file()
        assert not (transcripts / "talk.json").exists()

    def test_transcripts_only_does_not_invoke_missing(self, iw, dirs, monkeypatch):
        inbox, recordings, transcripts = dirs
        (inbox / "clip.m4a").write_bytes(b"audio")
        (inbox / "talk.json").write_text('{"ok": true}', encoding="utf-8")
        called = {"ffmpeg": 0, "missing": 0}

        def boom_ffmpeg(_cmd):
            called["ffmpeg"] += 1
            raise AssertionError("ffmpeg should not run")

        def boom_missing(_cmd):
            called["missing"] += 1
            raise AssertionError("whispermlx-missing should not run")

        monkeypatch.setattr(iw, "run_ffmpeg", boom_ffmpeg)
        monkeypatch.setattr(iw, "run_whispermlx_missing", boom_missing)
        rc = iw.main(_once_args(inbox, recordings, transcripts, ["--no-watch-audio"]))
        assert rc == 0
        assert called == {"ffmpeg": 0, "missing": 0}
        assert (transcripts / "talk.json").read_text(encoding="utf-8") == '{"ok": true}'
        assert not (recordings / "clip.mp3").exists()


@pytest.mark.unit
class TestStemSkip:
    def test_skip_audio_when_recordings_has_stem(self, iw, dirs, monkeypatch):
        inbox, recordings, transcripts = dirs
        (inbox / "foo.m4a").write_bytes(b"new")
        (recordings / "foo.wav").write_bytes(b"old")
        monkeypatch.setattr(iw, "run_ffmpeg", lambda _cmd: (_ for _ in ()).throw(
            AssertionError("should skip")
        ))
        monkeypatch.setattr(iw, "run_whispermlx_missing", lambda _cmd: 0)
        rc = iw.main(
            _once_args(inbox, recordings, transcripts, ["--no-watch-transcripts"])
        )
        assert rc == 0
        assert not (recordings / "foo.mp3").exists()

    def test_skip_transcript_when_dest_has_stem(self, iw, dirs, monkeypatch):
        inbox, recordings, transcripts = dirs
        (inbox / "foo.srt").write_text("new", encoding="utf-8")
        (transcripts / "foo.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(iw, "run_whispermlx_missing", lambda _cmd: 0)
        rc = iw.main(_once_args(inbox, recordings, transcripts, ["--no-watch-audio"]))
        assert rc == 0
        assert not (transcripts / "foo.srt").exists()
        assert (transcripts / "foo.json").read_text(encoding="utf-8") == "{}"


@pytest.mark.unit
class TestTranscriptCopy:
    def test_copy_preserves_bytes_and_basename(self, iw, dirs, monkeypatch):
        inbox, recordings, transcripts = dirs
        payload = '{"segments": []}\n'
        (inbox / "session.json").write_text(payload, encoding="utf-8")
        monkeypatch.setattr(iw, "run_whispermlx_missing", lambda _cmd: 0)
        rc = iw.main(_once_args(inbox, recordings, transcripts, ["--no-watch-audio"]))
        assert rc == 0
        dest = transcripts / "session.json"
        assert dest.read_text(encoding="utf-8") == payload
        assert (inbox / "session.json").is_file()

    def test_force_overwrites_transcript(self, iw, dirs, monkeypatch):
        inbox, recordings, transcripts = dirs
        (inbox / "foo.json").write_text("new", encoding="utf-8")
        (transcripts / "foo.json").write_text("old", encoding="utf-8")
        monkeypatch.setattr(iw, "run_whispermlx_missing", lambda _cmd: 0)
        rc = iw.main(
            _once_args(
                inbox, recordings, transcripts, ["--no-watch-audio", "--force"]
            )
        )
        assert rc == 0
        assert (transcripts / "foo.json").read_text(encoding="utf-8") == "new"


@pytest.mark.unit
class TestDryRun:
    def test_dry_run_does_not_call_ffmpeg_or_missing(self, iw, dirs, monkeypatch):
        inbox, recordings, transcripts = dirs
        (inbox / "clip.m4a").write_bytes(b"audio")
        (inbox / "talk.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(
            iw,
            "run_ffmpeg",
            lambda _cmd: (_ for _ in ()).throw(AssertionError("ffmpeg")),
        )
        monkeypatch.setattr(
            iw,
            "run_whispermlx_missing",
            lambda _cmd: (_ for _ in ()).throw(AssertionError("missing")),
        )
        rc = iw.main(_once_args(inbox, recordings, transcripts, ["--dry-run"]))
        assert rc == 0
        assert not list(recordings.iterdir())
        assert not list(transcripts.iterdir())


@pytest.mark.unit
class TestMissingInvocation:
    def test_once_invokes_missing_after_convert(self, iw, dirs, monkeypatch):
        inbox, recordings, transcripts = dirs
        (inbox / "clip.m4a").write_bytes(b"audio")
        seen: list[list[str]] = []
        monkeypatch.setattr(iw, "run_ffmpeg", _ok_ffmpeg)

        def capture(cmd):
            seen.append(list(cmd))
            return 0

        monkeypatch.setattr(iw, "run_whispermlx_missing", capture)
        rc = iw.main(
            _once_args(inbox, recordings, transcripts, ["--no-watch-transcripts"])
        )
        assert rc == 0
        assert (recordings / "clip.mp3").is_file()
        assert len(seen) == 1
        cmd = seen[0]
        assert "--source" in cmd and cmd[cmd.index("--source") + 1] == str(recordings)
        assert "--transcripts" in cmd and cmd[cmd.index("--transcripts") + 1] == str(
            transcripts
        )

    def test_once_invokes_missing_even_when_nothing_converted(
        self, iw, dirs, monkeypatch
    ):
        inbox, recordings, transcripts = dirs
        seen = {"n": 0}

        def capture(_cmd):
            seen["n"] += 1
            return 0

        monkeypatch.setattr(iw, "run_whispermlx_missing", capture)
        rc = iw.main(
            _once_args(inbox, recordings, transcripts, ["--no-watch-transcripts"])
        )
        assert rc == 0
        assert seen["n"] == 1


@pytest.mark.unit
class TestConfig:
    def test_cli_overrides_json(self, iw, tmp_path: Path, monkeypatch):
        monkeypatch.delenv(iw.CONFIG_ENV_VAR, raising=False)
        config_path = tmp_path / "cfg.json"
        config_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "inbox": "/from/file",
                    "recordings": "/rec/file",
                    "transcripts": "/tx/file",
                    "watch_audio": True,
                    "watch_transcripts": False,
                }
            ),
            encoding="utf-8",
        )
        iw.CONFIG_PATH = config_path
        args = iw.parse_args(["--inbox", "/from/cli", "--config", str(config_path)])
        cfg = iw.resolve_config(args, config_path=config_path)
        assert str(cfg.inbox) == "/from/cli"
        assert str(cfg.recordings) == "/rec/file"
        assert cfg.watch_audio is True
        assert cfg.watch_transcripts is False
        assert cfg.provenance.inbox == "cli"
        assert cfg.provenance.recordings == "json"

    def test_json_modes_survive_when_cli_omits_flags(self, iw, tmp_path: Path):
        config_path = tmp_path / "cfg.json"
        config_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "inbox": "/from/file",
                    "recordings": "/rec/file",
                    "transcripts": "/tx/file",
                    "watch_audio": False,
                    "watch_transcripts": True,
                    "recursive": True,
                }
            ),
            encoding="utf-8",
        )
        args = iw.parse_args(["--config", str(config_path)])
        cfg = iw.resolve_config(args, config_path=config_path)
        assert cfg.watch_audio is False
        assert cfg.watch_transcripts is True
        assert cfg.recursive is True


@pytest.mark.unit
class TestBackupAndDelete:
    def test_backup_copies_audio_original(self, iw, dirs, tmp_path: Path, monkeypatch):
        inbox, recordings, transcripts = dirs
        wav_backup = tmp_path / "wav"
        (inbox / "clip.m4a").write_bytes(b"audio")
        monkeypatch.setattr(iw, "run_ffmpeg", _ok_ffmpeg)
        monkeypatch.setattr(iw, "run_whispermlx_missing", lambda _cmd: 0)
        rc = iw.main(
            _once_args(
                inbox,
                recordings,
                transcripts,
                [
                    "--no-watch-transcripts",
                    "--backup-wav",
                    "--wav-backup",
                    str(wav_backup),
                ],
            )
        )
        assert rc == 0
        assert (recordings / "clip.mp3").is_file()
        assert (wav_backup / "clip.m4a").read_bytes() == b"audio"
        assert (inbox / "clip.m4a").is_file()

    def test_backup_and_delete_audio(self, iw, dirs, tmp_path: Path, monkeypatch):
        inbox, recordings, transcripts = dirs
        wav_backup = tmp_path / "wav"
        (inbox / "clip.m4a").write_bytes(b"audio")
        monkeypatch.setattr(iw, "run_ffmpeg", _ok_ffmpeg)
        monkeypatch.setattr(iw, "run_whispermlx_missing", lambda _cmd: 0)
        rc = iw.main(
            _once_args(
                inbox,
                recordings,
                transcripts,
                [
                    "--no-watch-transcripts",
                    "--backup-wav",
                    "--wav-backup",
                    str(wav_backup),
                    "--delete-originals",
                ],
            )
        )
        assert rc == 0
        assert (recordings / "clip.mp3").is_file()
        assert (wav_backup / "clip.m4a").read_bytes() == b"audio"
        assert not (inbox / "clip.m4a").exists()

    def test_delete_transcript_original(self, iw, dirs, monkeypatch):
        inbox, recordings, transcripts = dirs
        (inbox / "talk.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(iw, "run_whispermlx_missing", lambda _cmd: 0)
        rc = iw.main(
            _once_args(
                inbox,
                recordings,
                transcripts,
                ["--no-watch-audio", "--delete-originals"],
            )
        )
        assert rc == 0
        assert (transcripts / "talk.json").read_text(encoding="utf-8") == "{}"
        assert not (inbox / "talk.json").exists()

    def test_failed_backup_skips_delete(self, iw, dirs, tmp_path: Path, monkeypatch):
        inbox, recordings, transcripts = dirs
        wav_backup = tmp_path / "wav"
        (inbox / "clip.m4a").write_bytes(b"audio")
        monkeypatch.setattr(iw, "run_ffmpeg", _ok_ffmpeg)
        monkeypatch.setattr(iw, "run_whispermlx_missing", lambda _cmd: 0)

        def boom_backup(_src, _dest):
            raise OSError("disk full")

        monkeypatch.setattr(iw, "backup_original_to_wav", boom_backup)
        rc = iw.main(
            _once_args(
                inbox,
                recordings,
                transcripts,
                [
                    "--no-watch-transcripts",
                    "--backup-wav",
                    "--wav-backup",
                    str(wav_backup),
                    "--delete-originals",
                ],
            )
        )
        assert rc == 0
        assert (recordings / "clip.mp3").is_file()
        assert (inbox / "clip.m4a").is_file()

    def test_dry_run_does_not_backup_or_delete(
        self, iw, dirs, tmp_path: Path, monkeypatch
    ):
        inbox, recordings, transcripts = dirs
        wav_backup = tmp_path / "wav"
        (inbox / "clip.m4a").write_bytes(b"audio")
        monkeypatch.setattr(
            iw,
            "run_ffmpeg",
            lambda _cmd: (_ for _ in ()).throw(AssertionError("ffmpeg")),
        )
        monkeypatch.setattr(
            iw,
            "run_whispermlx_missing",
            lambda _cmd: (_ for _ in ()).throw(AssertionError("missing")),
        )
        rc = iw.main(
            _once_args(
                inbox,
                recordings,
                transcripts,
                [
                    "--dry-run",
                    "--backup-wav",
                    "--wav-backup",
                    str(wav_backup),
                    "--delete-originals",
                    "--no-watch-transcripts",
                ],
            )
        )
        assert rc == 0
        assert (inbox / "clip.m4a").is_file()
        assert not wav_backup.exists() or not any(wav_backup.iterdir())

    def test_delete_and_move_processed_rejected(self, iw, dirs, tmp_path: Path):
        inbox, recordings, transcripts = dirs
        processed = tmp_path / "done"
        rc = iw.main(
            _once_args(
                inbox,
                recordings,
                transcripts,
                [
                    "--delete-originals",
                    "--move-processed",
                    str(processed),
                    "--no-watch-transcripts",
                ],
            )
        )
        assert rc == 2

    def test_backup_name_conflict_suffix(self, iw, tmp_path: Path):
        wav_backup = tmp_path / "wav"
        wav_backup.mkdir()
        (wav_backup / "clip.m4a").write_bytes(b"old")
        src = tmp_path / "clip.m4a"
        src.write_bytes(b"new")
        dest = iw.unique_backup_path(wav_backup, src)
        assert dest.name == "clip_1.m4a"


def test_refuses_managed_library_root_as_transcripts_dest(iw, tmp_path: Path) -> None:
    library = tmp_path / "transcripts"
    library.mkdir()
    (library / "metadata").mkdir()
    originals = library / "originals"
    originals.mkdir()
    assert iw.looks_like_managed_library_root(library)
    assert not iw.looks_like_managed_library_root(originals)

    inbox = tmp_path / "inbox"
    recordings = tmp_path / "recordings"
    inbox.mkdir()
    recordings.mkdir()
    cfg = iw.EffectiveConfig(
        inbox=inbox,
        recordings=recordings,
        transcripts=library,
        env_file=tmp_path / "whisperx.env",
        whispermlx_missing=tmp_path / "whispermlx-missing.py",
        ffmpeg=None,
        watch_audio=True,
        watch_transcripts=False,
        recursive=False,
        interval_seconds=5,
        move_processed=None,
        wav_backup=None,
        backup_wavs=False,
        delete_originals=False,
        provenance=iw.ConfigProvenance(),
    )
    err = iw.validate_layout(cfg)
    assert err is not None
    assert "originals" in err


@pytest.mark.unit
class TestSkipSerialForwarding:
    def test_build_missing_cmd_appends_skip_serial(self, iw, tmp_path: Path):
        missing = tmp_path / "whispermlx-missing.py"
        missing.write_text("# stub\n", encoding="utf-8")
        recordings = tmp_path / "recordings"
        transcripts = tmp_path / "originals"
        cmd = iw.build_missing_cmd(
            missing,
            recordings=recordings,
            transcripts=transcripts,
            env_file=None,
            skip_serial=True,
        )
        assert "--skip-serial" in cmd
        assert str(recordings) in cmd

    def test_build_missing_cmd_omits_flag_by_default(self, iw, tmp_path: Path):
        missing = tmp_path / "whispermlx-missing.py"
        missing.write_text("# stub\n", encoding="utf-8")
        cmd = iw.build_missing_cmd(
            missing,
            recordings=tmp_path / "rec",
            transcripts=tmp_path / "tx",
            env_file=None,
        )
        assert "--skip-serial" not in cmd

    def test_cli_enables_skip_serial(self, iw, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(iw, "CONFIG_PATH", tmp_path / "noconfig.json")
        args = iw.parse_args(
            [
                "--once",
                "--inbox",
                str(tmp_path / "inbox"),
                "--recordings",
                str(tmp_path / "rec"),
                "--transcripts",
                str(tmp_path / "tx"),
                "--skip-serial",
            ]
        )
        cfg = iw.resolve_config(args, config_path=tmp_path / "noconfig.json")
        assert cfg.skip_serial is True


@pytest.mark.unit
class TestAdmit:
    def test_default_off(self, iw, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("INBOX_WATCH_ADMIT", raising=False)
        args = iw.parse_args(
            [
                "--once",
                "--inbox",
                str(tmp_path / "inbox"),
                "--recordings",
                str(tmp_path / "rec"),
                "--transcripts",
                str(tmp_path / "tx"),
            ]
        )
        cfg = iw.resolve_config(args, config_path=tmp_path / "noconfig.json")
        assert cfg.admit_to_library is False

    def test_cli_enables_admit(self, iw, tmp_path: Path):
        args = iw.parse_args(
            [
                "--once",
                "--inbox",
                str(tmp_path / "inbox"),
                "--recordings",
                str(tmp_path / "rec"),
                "--transcripts",
                str(tmp_path / "tx"),
                "--admit",
            ]
        )
        cfg = iw.resolve_config(args, config_path=tmp_path / "noconfig.json")
        assert cfg.admit_to_library is True

    def test_env_enables_admit(self, iw, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("INBOX_WATCH_ADMIT", "1")
        args = iw.parse_args(
            [
                "--once",
                "--inbox",
                str(tmp_path / "inbox"),
                "--recordings",
                str(tmp_path / "rec"),
                "--transcripts",
                str(tmp_path / "tx"),
            ]
        )
        cfg = iw.resolve_config(args, config_path=tmp_path / "noconfig.json")
        assert cfg.admit_to_library is True

    def test_transcripts_root_parent_of_originals(self, iw, tmp_path: Path):
        originals = tmp_path / "transcripts" / "originals"
        assert iw.transcripts_root_for_admit(originals) == tmp_path / "transcripts"
        other = tmp_path / "inbox-json"
        assert iw.transcripts_root_for_admit(other) == other

    def test_build_admit_cmd(self, iw, tmp_path: Path):
        python = tmp_path / "bin" / "python"
        transcripts = tmp_path / "transcripts" / "originals"
        cmd = iw.build_admit_cmd(python, transcripts=transcripts)
        assert cmd[:3] == [str(python), "-m", "transcriptx.admit_originals"]
        assert "--dir" in cmd
        assert str(transcripts) in cmd
        assert "--transcripts-root" in cmd
        assert str(tmp_path / "transcripts") in cmd
        assert "--dry-run" not in cmd
        dry = iw.build_admit_cmd(python, transcripts=transcripts, dry_run=True)
        assert "--dry-run" in dry

    def test_main_invokes_admit_after_missing(self, iw, dirs, monkeypatch):
        inbox, recordings, transcripts = dirs
        (inbox / "clip.m4a").write_bytes(b"audio")
        monkeypatch.setattr(iw, "run_ffmpeg", _ok_ffmpeg)
        monkeypatch.setattr(iw, "run_whispermlx_missing", lambda _cmd: 0)
        monkeypatch.setattr(
            iw, "find_admit_python", lambda _explicit: Path("/venv/bin/python")
        )
        seen: list[list[str]] = []

        def capture(cmd):
            seen.append(list(cmd))
            return 0

        monkeypatch.setattr(iw, "run_admit_originals", capture)
        rc = iw.main(
            _once_args(
                inbox, recordings, transcripts, ["--no-watch-transcripts", "--admit"]
            )
        )
        assert rc == 0
        assert seen
        assert "transcriptx.admit_originals" in seen[0]

    def test_main_skips_admit_by_default(self, iw, dirs, monkeypatch):
        inbox, recordings, transcripts = dirs
        (inbox / "clip.m4a").write_bytes(b"audio")
        monkeypatch.setattr(iw, "run_ffmpeg", _ok_ffmpeg)
        monkeypatch.setattr(iw, "run_whispermlx_missing", lambda _cmd: 0)

        def boom(_cmd):
            raise AssertionError("admit should not run")

        monkeypatch.setattr(iw, "run_admit_originals", boom)
        rc = iw.main(
            _once_args(inbox, recordings, transcripts, ["--no-watch-transcripts"])
        )
        assert rc == 0


@pytest.mark.unit
class TestWaitForDirectory:
    def test_returns_true_when_dir_exists(self, iw, tmp_path: Path):
        assert iw.wait_for_directory(tmp_path, interval_seconds=0.01) is True

    def test_timeout_when_missing(self, iw, tmp_path: Path):
        missing = tmp_path / "usb-inbox"
        assert (
            iw.wait_for_directory(
                missing, interval_seconds=0.01, timeout_seconds=0.05
            )
            is False
        )
        assert not missing.exists()

