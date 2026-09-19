"""Tests for scripts/voice-note-watch.py."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "voice-note-watch.py"
)
_INBOX_WATCH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "inbox-watch.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("voice_note_watch", _SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["voice_note_watch"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def vn():
    return _load_module()


@pytest.fixture(scope="module")
def iw(vn):
    return vn.iw


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("VOICE_NOTE_WATCH_"):
            monkeypatch.delenv(key, raising=False)


def _write_sibling(
    path: Path,
    inbox: Path,
    recordings: Path,
    transcripts: Path,
    *,
    recursive: bool = False,
) -> None:
    path.write_text(
        json.dumps(
            {
                "inbox": str(inbox),
                "recordings": str(recordings),
                "transcripts": str(transcripts),
                "recursive": recursive,
            }
        ),
        encoding="utf-8",
    )


def _layout(tmp_path: Path, *, recursive: bool = False):
    library = tmp_path / "RECORD"
    inbox = library / "braindump"
    inbox.mkdir(parents=True)
    recordings = tmp_path / "recordings"
    originals = tmp_path / "transcripts" / "originals"
    recordings.mkdir()
    originals.mkdir(parents=True)
    audio = tmp_path / "voice-notes" / "audio"
    notes = tmp_path / "voice-notes" / "text"
    sibling = tmp_path / "inbox-watch.json"
    _write_sibling(
        sibling, library, recordings, originals, recursive=recursive
    )
    return {
        "library": library,
        "inbox": inbox,
        "recordings": recordings,
        "originals": originals,
        "audio": audio,
        "notes": notes,
        "sibling": sibling,
        "config": tmp_path / "voice-note-watch.json",
        "ffmpeg": tmp_path / "ffmpeg",
        "whisper": tmp_path / "whispermlx",
    }


def _args(layout: dict, extra: list[str] | None = None, *, duration: str = "180") -> list[str]:
    args = [
        "--once",
        "--config",
        str(layout["config"]),
        "--inbox",
        str(layout["inbox"]),
        "--audio-dir",
        str(layout["audio"]),
        "--notes-dir",
        str(layout["notes"]),
        "--library-watch-config",
        str(layout["sibling"]),
        "--ffmpeg",
        str(layout["ffmpeg"]),
        "--whispermlx",
        str(layout["whisper"]),
        "--model",
        "large-v3",
        "--language",
        "en",
        "--stability-checks",
        "1",
        "--no-stage-local",
    ]
    if duration:
        args.extend(["--max-duration-seconds", duration])
    if extra:
        args.extend(extra)
    return args


def _install_fake(
    monkeypatch,
    vn,
    *,
    duration: str | None = "00:00:30.00",
    help_text: str = "usage: whispermlx\n  -f, --output_format {json,txt,srt}\n",
    write_txt: bool = True,
    write_json: bool = False,
    txt_body: str = "I need to buy milk. Is the shop open? The sky is green.",
):
    calls: list[list[str]] = []

    def fake(cmd, **_kwargs):
        argv = [str(part) for part in cmd]
        calls.append(argv)
        if "--help" in argv:
            return MagicMock(returncode=0, stdout=help_text, stderr="")
        if "--output_dir" in argv:
            out = Path(argv[argv.index("--output_dir") + 1])
            out.mkdir(parents=True, exist_ok=True)
            stem = Path(argv[1]).stem
            if write_txt:
                (out / f"{stem}.txt").write_text(txt_body, encoding="utf-8")
            if write_json:
                (out / f"{stem}.json").write_text("{}", encoding="utf-8")
            return MagicMock(returncode=0, stdout="", stderr="")
        if "-c:a" in argv:
            dest = Path(argv[-1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"mp3")
            return MagicMock(returncode=0, stdout="", stderr="")
        if "-i" in argv:
            if duration is None:
                stderr = "Duration: N/A, bitrate: N/A"
            else:
                stderr = f"Duration: {duration}, start: 0.000000, bitrate: 64 kb/s"
            return MagicMock(returncode=1, stdout="", stderr=stderr)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(vn.subprocess, "run", fake)
    return calls


def _drop(inbox: Path, name: str = "note.wav", payload: bytes = b"raw-audio") -> Path:
    path = inbox / name
    path.write_bytes(payload)
    return path


@pytest.mark.unit
class TestSourceBoundary:
    def test_does_not_import_transcriptx(self):
        text = _SCRIPT_PATH.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert "transcriptx" not in stripped
        assert "admit_originals" not in text

    def test_admit_flags_are_rejected(self, vn, tmp_path: Path):
        layout = _layout(tmp_path)
        assert vn.main(_args(layout, ["--admit"])) == 2
        assert vn.main(_args(layout, ["--auto-name"])) == 2


@pytest.mark.unit
class TestIsolation:
    def test_missing_sibling_config(self, vn, tmp_path: Path):
        layout = _layout(tmp_path)
        layout["sibling"] = tmp_path / "missing-inbox-watch.json"
        rc = vn.main(_args(layout))
        assert rc == 2

    def test_shared_inbox_rejected(self, vn, tmp_path: Path, capsys):
        layout = _layout(tmp_path)
        layout["inbox"] = layout["library"]
        rc = vn.main(_args(layout))
        assert rc == 2
        assert "must not be the library inbox" in capsys.readouterr().err

    def test_parent_inbox_rejected(self, vn, tmp_path: Path, capsys):
        layout = _layout(tmp_path)
        layout["inbox"] = tmp_path
        rc = vn.main(_args(layout))
        assert rc == 2
        assert "must not contain the library inbox" in capsys.readouterr().err

    def test_subdirectory_rejected_when_library_watcher_is_recursive(
        self, vn, tmp_path: Path, capsys
    ):
        layout = _layout(tmp_path, recursive=True)
        rc = vn.main(_args(layout))
        assert rc == 2
        assert "recursive" in capsys.readouterr().err

    def test_audio_dir_must_not_be_library_recordings(self, vn, tmp_path: Path):
        layout = _layout(tmp_path)
        layout["audio"] = layout["recordings"]
        assert vn.main(_args(layout)) == 2

    def test_notes_dir_must_not_sit_under_originals(self, vn, tmp_path: Path):
        layout = _layout(tmp_path)
        notes = layout["originals"] / "notes"
        notes.mkdir()
        layout["notes"] = notes
        assert vn.main(_args(layout)) == 2

    def test_max_duration_required(self, vn, tmp_path: Path, capsys):
        layout = _layout(tmp_path)
        rc = vn.main(_args(layout, duration=""))
        assert rc == 2
        assert "max_duration_seconds" in capsys.readouterr().err


@pytest.mark.unit
class TestCapAndTranscribe:
    def test_over_cap_leaves_source_and_does_not_encode(
        self, vn, tmp_path: Path, monkeypatch
    ):
        layout = _layout(tmp_path)
        src = _drop(layout["inbox"])
        before = src.read_bytes()
        calls = _install_fake(monkeypatch, vn, duration="00:10:00.00")
        rc = vn.main(_args(layout, duration="180"))
        assert rc == 0
        assert src.read_bytes() == before
        assert not any("-c:a" in cmd for cmd in calls)
        assert not any(layout["whisper"].name in Path(cmd[0]).name and "--help" in cmd for cmd in calls)
        assert not any("--output_dir" in cmd for cmd in calls)
        assert not layout["audio"].exists() or not any(layout["audio"].glob("*.mp3"))
        assert not (layout["library"] / src.name).exists()

    def test_over_cap_copies_once_to_library_inbox(
        self, vn, tmp_path: Path, monkeypatch
    ):
        layout = _layout(tmp_path)
        src = _drop(layout["inbox"], payload=b"long-note")
        calls = _install_fake(monkeypatch, vn, duration="00:05:00.00")
        copies: list[Path] = []
        real_copy = vn.shutil.copy2

        def counting(src_path, dest_path, *args, **kwargs):
            copies.append(Path(dest_path))
            return real_copy(src_path, dest_path, *args, **kwargs)

        monkeypatch.setattr(vn.shutil, "copy2", counting)
        extra = ["--library-inbox", str(layout["library"])]
        assert vn.main(_args(layout, extra, duration="30")) == 0
        dest = layout["library"] / src.name
        assert dest.is_file()
        assert dest.read_bytes() == b"long-note"
        assert src.read_bytes() == b"long-note"
        assert len(copies) == 1
        first_mtime = dest.stat().st_mtime_ns
        assert vn.main(_args(layout, extra, duration="30")) == 0
        assert len(copies) == 1
        assert dest.stat().st_mtime_ns == first_mtime
        state = json.loads(
            (layout["config"].parent / "voice-note-watch-state.json").read_text(
                encoding="utf-8"
            )
        )
        assert str(src.resolve()) in state["overflow"]
        assert not any("-c:a" in cmd for cmd in calls)

    def test_unknown_duration_refused(self, vn, tmp_path: Path, monkeypatch):
        layout = _layout(tmp_path)
        src = _drop(layout["inbox"])
        before = src.read_bytes()
        calls = _install_fake(monkeypatch, vn, duration=None)
        assert vn.main(_args(layout)) == 0
        assert src.read_bytes() == before
        assert not any("-c:a" in cmd for cmd in calls)
        assert not any("--output_dir" in cmd for cmd in calls)

    def test_under_cap_writes_plain_text_not_originals_json(
        self, vn, iw, tmp_path: Path, monkeypatch
    ):
        layout = _layout(tmp_path)
        src = _drop(layout["inbox"])
        calls = _install_fake(monkeypatch, vn, duration="00:00:20.00")
        assert vn.main(_args(layout, duration="180")) == 0
        encode = next(cmd for cmd in calls if "-c:a" in cmd)
        partial = layout["audio"] / f".voice-note-watch.{src.stem}.mp3.partial"
        expected = iw.build_ffmpeg_cmd(layout["ffmpeg"], src, partial)
        assert encode == expected
        whisper = next(cmd for cmd in calls if "--output_dir" in cmd)
        assert whisper[whisper.index("-f") + 1] == "txt"
        assert "--diarize" not in whisper
        assert "--hf_token" not in whisper
        assert (layout["notes"] / "note.txt").is_file()
        assert not (layout["notes"] / "note.json").exists()
        assert not (layout["notes"] / "note.draft.md").exists()
        assert list(layout["originals"].rglob("*.json")) == []
        assert (layout["audio"] / "note.mp3").is_file()

    def test_existing_text_skips_encode(self, vn, tmp_path: Path, monkeypatch):
        layout = _layout(tmp_path)
        layout["notes"].mkdir(parents=True)
        (layout["notes"] / "note.txt").write_text("already", encoding="utf-8")
        _drop(layout["inbox"])
        calls = _install_fake(monkeypatch, vn)
        assert vn.main(_args(layout)) == 0
        assert not any("-c:a" in cmd or "--output_dir" in cmd for cmd in calls)
        assert (layout["notes"] / "note.txt").read_text(encoding="utf-8") == "already"

    def test_dry_run_writes_nothing(self, vn, tmp_path: Path, monkeypatch):
        layout = _layout(tmp_path)
        src = _drop(layout["inbox"])
        before = src.read_bytes()
        calls = _install_fake(monkeypatch, vn, duration="00:00:10.00")
        assert vn.main(_args(layout, ["--dry-run"])) == 0
        assert src.read_bytes() == before
        assert not layout["audio"].exists()
        assert not layout["notes"].exists()
        assert not any("-c:a" in cmd or "--output_dir" in cmd for cmd in calls)
        assert not (layout["config"].parent / "voice-note-watch-state.json").exists()

    def test_json_only_engine_output_is_not_promoted(
        self, vn, tmp_path: Path, monkeypatch
    ):
        layout = _layout(tmp_path)
        calls = _install_fake(
            monkeypatch, vn, duration="00:00:10.00", write_txt=False, write_json=True
        )
        _drop(layout["inbox"])
        assert vn.main(_args(layout)) == 1
        assert not (layout["notes"] / "note.txt").exists()
        assert not (layout["notes"] / "note.json").exists()
        leftover = list((layout["notes"] / ".whispermlx-voice-note").rglob("*.json"))
        assert leftover
        assert list(layout["originals"].rglob("*.json")) == []
        assert any("--output_dir" in cmd for cmd in calls)

    def test_txt_not_advertised_exits_before_encode(
        self, vn, tmp_path: Path, monkeypatch
    ):
        layout = _layout(tmp_path)
        _drop(layout["inbox"])
        calls = _install_fake(
            monkeypatch,
            vn,
            duration="00:00:10.00",
            help_text="usage: whispermlx\n  -f, --output_format json\n",
        )
        assert vn.main(_args(layout)) == 2
        assert not any("-c:a" in cmd for cmd in calls)
        assert not (layout["audio"] / "note.mp3").exists()


@pytest.mark.unit
class TestTriage:
    def test_draft_sections(self, vn):
        draft = vn.build_draft(
            "I need to buy milk. Is the shop open? The sky is green."
        )
        assert "Not admitted" in draft
        assert "## Todos" in draft
        assert "I need to buy milk." in draft
        assert "## Questions" in draft
        assert "Is the shop open?" in draft
        assert "## Claims" in draft
        assert "unverified: The sky is green." in draft

    def test_triage_flag_writes_draft_only_when_asked(
        self, vn, tmp_path: Path, monkeypatch
    ):
        layout = _layout(tmp_path)
        _drop(layout["inbox"])
        _install_fake(monkeypatch, vn, duration="00:00:15.00")
        assert vn.main(_args(layout, ["--triage"])) == 0
        draft = (layout["notes"] / "note.draft.md").read_text(encoding="utf-8")
        assert "## Todos" in draft
        assert "## Questions" in draft
        assert "## Claims" in draft
        assert "unverified:" in draft
        assert "Not admitted" in draft

        layout2 = _layout(tmp_path / "off")
        _drop(layout2["inbox"])
        _install_fake(monkeypatch, vn, duration="00:00:15.00")
        assert vn.main(_args(layout2)) == 0
        assert not (layout2["notes"] / "note.draft.md").exists()
