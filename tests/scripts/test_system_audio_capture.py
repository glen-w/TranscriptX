"""Tests for scripts/system-audio-capture.py (roadmap G5)."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "scripts"
    / "system-audio-capture.py"
)

_AVFOUNDATION_LIST = """\
[AVFoundation indev @ 0x0] AVFoundation video devices:
[AVFoundation indev @ 0x0] [0] FaceTime HD Camera
[AVFoundation indev @ 0x0] AVFoundation audio devices:
[AVFoundation indev @ 0x0] [0] MacBook Pro Microphone
[AVFoundation indev @ 0x0] [1] BlackHole 2ch
[AVFoundation indev @ 0x0] [2] Multi-Output Device
"""


def _load_module():
    spec = importlib.util.spec_from_file_location("system_audio_capture", _SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["system_audio_capture"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cap():
    return _load_module()


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("SYSTEM_AUDIO_CAPTURE_"):
            monkeypatch.delenv(key, raising=False)
        if key.startswith("INBOX_WATCH_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SYSTEM_AUDIO_CAPTURE_ALLOW_NON_DARWIN", "1")


def _cfg(cap, tmp_path: Path, **overrides):
    recordings = tmp_path / "recordings" / "capture"
    originals = tmp_path / "transcripts" / "originals"
    sessions = tmp_path / "data" / "capture" / "sessions"
    recordings.mkdir(parents=True, exist_ok=True)
    originals.mkdir(parents=True, exist_ok=True)
    sessions.mkdir(parents=True, exist_ok=True)
    data = {
        "recordings": recordings,
        "transcripts": originals,
        "sessions_dir": sessions,
        "env_file": None,
        "whispermlx": Path("/usr/local/bin/whispermlx"),
        "ffmpeg": Path("/usr/bin/ffmpeg"),
        "admit_python": None,
        "library_inbox": None,
        "watcher_inbox": None,
        "voice_note_inbox": None,
        "model": "large-v3",
        "language": "en",
        "device": "BlackHole 2ch",
        "mix_mic_device": "",
        "max_duration_seconds": 7200,
        "min_free_bytes": 0,
        "silent_input_seconds": 5,
        "silent_rms_threshold": 80,
    }
    data.update(overrides)
    return cap.EffectiveConfig(**data)


@pytest.mark.unit
def test_script_does_not_import_transcriptx():
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    assert "\nimport transcriptx" not in source
    assert "\nfrom transcriptx" not in source
    assert "transcriptx.admit_originals" in source


@pytest.mark.unit
def test_parse_avfoundation_devices(cap):
    devices = cap.parse_avfoundation_devices(_AVFOUNDATION_LIST)
    assert devices == [
        (0, "MacBook Pro Microphone"),
        (1, "BlackHole 2ch"),
        (2, "Multi-Output Device"),
    ]


@pytest.mark.unit
def test_match_blackhole_and_mic(cap):
    devices = cap.parse_avfoundation_devices(_AVFOUNDATION_LIST)
    hole = cap.match_audio_device(devices, None, require_blackhole=True)
    mic = cap.match_mic_device(devices, None)
    assert hole == (1, "BlackHole 2ch")
    assert mic == (0, "MacBook Pro Microphone")
    named = cap.match_audio_device(devices, "BlackHole 2ch", require_blackhole=True)
    assert named == (1, "BlackHole 2ch")


@pytest.mark.unit
def test_build_record_cmd_system_only_and_mix(cap):
    wav = Path("/tmp/session.wav")
    cmd = cap.build_record_cmd("ffmpeg", "BlackHole 2ch", wav)
    assert cmd[:6] == ["ffmpeg", "-nostdin", "-y", "-f", "avfoundation", "-i"]
    assert ":BlackHole 2ch" in cmd
    assert "-filter_complex" not in cmd
    mixed = cap.build_record_cmd(
        "ffmpeg", "BlackHole 2ch", wav, mix_mic_name="MacBook Pro Microphone"
    )
    assert mixed.count("-f") == 2
    assert "amix=inputs=2:duration=longest:dropout_transition=0" in mixed
    capped = cap.build_record_cmd(
        "ffmpeg", "BlackHole 2ch", wav, max_duration_seconds=7200
    )
    assert capped[capped.index("-t") + 1] == "7200"


@pytest.mark.unit
def test_whispermlx_cmd_never_diarizes_by_default(cap):
    cmd = cap.build_whispermlx_cmd(
        Path("whispermlx"),
        Path("/tmp/a.mp3"),
        Path("/tmp/out"),
        model="large-v3",
        language="en",
        diarize=False,
    )
    assert "--diarize" not in cmd
    assert "HF_TOKEN" not in cmd
    assert cmd[cmd.index("-f") + 1] == "json"
    with_d = cap.build_whispermlx_cmd(
        Path("whispermlx"),
        Path("/tmp/a.mp3"),
        Path("/tmp/out"),
        model="large-v3",
        language="en",
        diarize=True,
    )
    assert "--diarize" in with_d


@pytest.mark.unit
def test_layout_rejects_shared_inboxes_and_library_root(cap, tmp_path):
    inbox = tmp_path / "RECORD"
    inbox.mkdir()
    (inbox / "capture").mkdir()
    library = tmp_path / "library"
    (library / "metadata").mkdir(parents=True)
    cfg = _cfg(
        cap,
        tmp_path,
        recordings=inbox / "capture",
        library_inbox=inbox,
        transcripts=library,
    )
    err = cap.validate_layout(cfg)
    assert err is not None

    ok = _cfg(cap, tmp_path, library_inbox=tmp_path / "other-inbox")
    (tmp_path / "other-inbox").mkdir()
    assert cap.validate_layout(ok) is None

    same = _cfg(
        cap,
        tmp_path,
        recordings=inbox,
        library_inbox=inbox,
    )
    err_same = cap.validate_layout(same)
    assert err_same is not None


@pytest.mark.unit
def test_layout_rejects_g2_and_g4_folders(cap, tmp_path):
    g2 = tmp_path / "g2-inbox"
    g4 = tmp_path / "voice-notes"
    g2.mkdir()
    g4.mkdir()
    cfg = _cfg(cap, tmp_path, watcher_inbox=g2, recordings=g2)
    assert cap.validate_layout(cfg) is not None
    cfg4 = _cfg(cap, tmp_path, voice_note_inbox=g4, recordings=g4)
    assert cap.validate_layout(cfg4) is not None


@pytest.mark.unit
def test_single_active_session(cap, tmp_path, monkeypatch):
    cfg = _cfg(cap, tmp_path)
    monkeypatch.setattr(
        cap,
        "probe_ffmpeg_devices",
        lambda ffmpeg: (
            [(1, "BlackHole 2ch")],
            "",
        ),
    )
    monkeypatch.setattr(cap, "spawn_ffmpeg", lambda cmd, log: 4242)
    monkeypatch.setattr(cap, "pid_alive", lambda pid: pid == 4242)
    monkeypatch.setattr(cap.iw, "find_ffmpeg", lambda explicit: Path("/usr/bin/ffmpeg"))
    first = cap.cmd_start(cfg, title="one")
    assert first == 0
    second = cap.cmd_start(cfg, title="two")
    assert second == 2
    active = cap.find_active_session(cfg.sessions_dir)
    assert active is not None
    assert active.title == "one"
    assert active.ffmpeg_pid == 4242


@pytest.mark.unit
def test_duration_cap_reclaim_marks_recorded(cap, tmp_path, monkeypatch):
    cfg = _cfg(cap, tmp_path, max_duration_seconds=60)
    session = cap.CaptureSession(
        session_id="cap-1",
        state="recording",
        ffmpeg_pid=888,
        wav_path=str(cfg.recordings / "cap-1.wav"),
        started_at="20200101T000000Z",
    )
    cap.save_session(cfg.sessions_dir, session)
    monkeypatch.setattr(cap, "pid_alive", lambda pid: False)
    reclaimed = cap.reclaim_abandoned(
        cfg.sessions_dir, max_duration_seconds=cfg.max_duration_seconds
    )
    assert len(reclaimed) == 1
    loaded = cap.load_session(cap.session_path(cfg.sessions_dir, "cap-1"))
    assert loaded.state == "recorded"
    assert any("max_duration_seconds" in warning for warning in loaded.warnings)


@pytest.mark.unit
def test_abandoned_when_pid_dead(cap, tmp_path, monkeypatch):
    cfg = _cfg(cap, tmp_path)
    session = cap.CaptureSession(
        session_id="dead-1",
        state="recording",
        ffmpeg_pid=999999,
        wav_path=str(cfg.recordings / "dead-1.wav"),
        started_at=cap.utc_now(),
    )
    cap.save_session(cfg.sessions_dir, session)
    monkeypatch.setattr(cap, "pid_alive", lambda pid: False)
    reclaimed = cap.reclaim_abandoned(cfg.sessions_dir)
    assert len(reclaimed) == 1
    loaded = cap.load_session(cap.session_path(cfg.sessions_dir, "dead-1"))
    assert loaded.state == "abandoned"
    assert loaded.wav_path.endswith("dead-1.wav")


@pytest.mark.unit
def test_stop_no_transcribe(cap, tmp_path, monkeypatch):
    cfg = _cfg(cap, tmp_path)
    wav = cfg.recordings / "s1.wav"
    wav.write_bytes(b"RIFF")
    session = cap.CaptureSession(
        session_id="s1",
        state="recording",
        ffmpeg_pid=123,
        wav_path=str(wav),
        started_at="20261026T000000Z",
    )
    cap.save_session(cfg.sessions_dir, session)
    monkeypatch.setattr(cap, "pid_alive", lambda pid: True)
    monkeypatch.setattr(cap, "stop_ffmpeg", lambda pid, timeout=8.0: None)
    monkeypatch.setattr(cap, "maybe_warn_silent", lambda cfg, session: None)
    code = cap.cmd_stop(cfg, session_id="s1", transcribe=False)
    assert code == 0
    loaded = cap.load_session(cap.session_path(cfg.sessions_dir, "s1"))
    assert loaded.state == "recorded"
    assert loaded.json_path is None


@pytest.mark.unit
def test_finalize_convert_transcribe_admit_argv(cap, tmp_path, monkeypatch):
    cfg = _cfg(cap, tmp_path)
    wav = cfg.recordings / "fin.wav"
    wav.write_bytes(b"RIFF")
    session = cap.CaptureSession(
        session_id="fin",
        state="abandoned",
        wav_path=str(wav),
        started_at="20261026T000000Z",
        stopped_at="20261026T000100Z",
    )
    cap.save_session(cfg.sessions_dir, session)

    mp3 = wav.with_suffix(".mp3")
    monkeypatch.setattr(cap, "convert_wav", lambda cfg, wav_path: mp3)
    monkeypatch.setattr(
        cap,
        "transcribe_json",
        lambda cfg, mp3_path, diarize, dry_run: cfg.transcripts / "fin.json",
    )
    (cfg.transcripts / "fin.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        cap.iw,
        "find_admit_python",
        lambda explicit: Path("/venv/bin/python"),
    )
    captured = {}

    def _admit(cmd):
        captured["cmd"] = list(cmd)
        return 0

    monkeypatch.setattr(cap.iw, "run_admit_originals", _admit)
    monkeypatch.setattr(cap, "maybe_warn_silent", lambda cfg, session: None)
    code = cap.cmd_finalize(cfg, "fin", admit=True, diarize=False, dry_run=False)
    assert code == 0
    loaded = cap.load_session(cap.session_path(cfg.sessions_dir, "fin"))
    assert loaded.state == "admitted"
    assert captured["cmd"][:3] == [
        "/venv/bin/python",
        "-m",
        "transcriptx.admit_originals",
    ]
    assert "--dir" in captured["cmd"]
    assert "--diarize" not in cap.build_whispermlx_cmd(
        Path("whispermlx"), mp3, tmp_path, model="m", language="en", diarize=False
    )


@pytest.mark.unit
def test_convert_uses_inbox_watch_ffmpeg_settings(cap, tmp_path, monkeypatch):
    cfg = _cfg(cap, tmp_path)
    wav = cfg.recordings / "a.wav"
    wav.write_bytes(b"x")
    seen = {}

    def fake_run(cmd):
        seen["cmd"] = list(cmd)
        partial = Path(cmd[-1])
        partial.write_bytes(b"mp3")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cap.iw, "find_ffmpeg", lambda explicit: Path("/usr/bin/ffmpeg"))
    monkeypatch.setattr(cap.iw, "run_ffmpeg", fake_run)
    dest = cap.convert_wav(cfg, wav)
    assert dest == wav.with_suffix(".mp3")
    assert "-ac" in seen["cmd"]
    assert "1" in seen["cmd"]
    assert "16000" in seen["cmd"]
    assert "libmp3lame" in seen["cmd"]
    assert "64k" in seen["cmd"]


@pytest.mark.unit
def test_skip_existing_json(cap, tmp_path, monkeypatch):
    cfg = _cfg(cap, tmp_path)
    mp3 = cfg.recordings / "exists.mp3"
    mp3.write_bytes(b"x")
    dest = cfg.transcripts / "exists.json"
    dest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cap, "find_whispermlx", lambda explicit: Path("whispermlx"))
    ran = {"n": 0}

    def boom(*args, **kwargs):
        ran["n"] += 1
        raise AssertionError("should not spawn whispermlx")

    monkeypatch.setattr(cap.subprocess, "run", boom)
    out = cap.transcribe_json(cfg, mp3, diarize=False, dry_run=False)
    assert out == dest
    assert ran["n"] == 0


@pytest.mark.unit
def test_refuse_low_disk(cap, tmp_path, monkeypatch):
    cfg = _cfg(cap, tmp_path, min_free_bytes=10**12)
    monkeypatch.setattr(
        cap,
        "probe_ffmpeg_devices",
        lambda ffmpeg: (
            [(1, "BlackHole 2ch")],
            "",
        ),
    )
    monkeypatch.setattr(cap.iw, "find_ffmpeg", lambda explicit: Path("/usr/bin/ffmpeg"))
    monkeypatch.setattr(cap, "free_bytes", lambda path: 100)
    code = cap.cmd_start(cfg)
    assert code == 2


@pytest.mark.unit
def test_silent_wav_warning(cap, tmp_path):
    cfg = _cfg(cap, tmp_path, silent_rms_threshold=80)
    wav = cfg.recordings / "quiet.wav"
    with open(wav, "wb") as handle:
        import wave as wave_mod

        with wave_mod.open(handle, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(16000)
            writer.writeframes(b"\x00\x00" * 1600)
    session = cap.CaptureSession(
        session_id="q",
        state="recorded",
        wav_path=str(wav),
    )
    cap.maybe_warn_silent(cfg, session)
    assert session.warnings
    assert "near-silent" in session.warnings[0]


@pytest.mark.unit
def test_require_darwin_without_allow(cap, monkeypatch):
    monkeypatch.delenv("SYSTEM_AUDIO_CAPTURE_ALLOW_NON_DARWIN", raising=False)
    monkeypatch.setattr(cap.sys, "platform", "linux")
    err = cap.require_darwin()
    assert err is not None
    assert "macOS-only" in err


@pytest.mark.unit
def test_dry_run_start_does_not_spawn(cap, tmp_path, monkeypatch):
    cfg = _cfg(cap, tmp_path)
    monkeypatch.setattr(
        cap,
        "probe_ffmpeg_devices",
        lambda ffmpeg: (
            [(1, "BlackHole 2ch")],
            "",
        ),
    )
    monkeypatch.setattr(cap.iw, "find_ffmpeg", lambda explicit: Path("/usr/bin/ffmpeg"))
    spawned = {"n": 0}

    def boom(*args, **kwargs):
        spawned["n"] += 1
        raise AssertionError("spawn")

    monkeypatch.setattr(cap, "spawn_ffmpeg", boom)
    code = cap.cmd_start(cfg, dry_run=True)
    assert code == 0
    assert spawned["n"] == 0
    assert cap.find_active_session(cfg.sessions_dir) is None


@pytest.mark.unit
def test_env_prefix_does_not_read_inbox_watch_admit(cap, tmp_path, monkeypatch):
    monkeypatch.setenv("INBOX_WATCH_ADMIT", "1")
    args = cap.parse_args(["--show-config", "--sessions-dir", str(tmp_path / "s")])
    cfg = cap.resolve_config(args)
    # admit is a stop flag, not a config default-on from inbox-watch
    assert not hasattr(cfg, "admit_to_library")


@pytest.mark.unit
def test_status_json_flag(cap):
    args = cap.parse_args(["status", "--json"])
    assert args.command == "status"
    assert args.as_json is True


@pytest.mark.unit
def test_mix_mic_requires_device(cap, tmp_path, monkeypatch):
    cfg = _cfg(cap, tmp_path)
    monkeypatch.setattr(
        cap,
        "probe_ffmpeg_devices",
        lambda ffmpeg: (
            [(1, "BlackHole 2ch")],
            "",
        ),
    )
    monkeypatch.setattr(cap.iw, "find_ffmpeg", lambda explicit: Path("/usr/bin/ffmpeg"))
    code = cap.cmd_start(cfg, mix_mic=True)
    assert code == 2
