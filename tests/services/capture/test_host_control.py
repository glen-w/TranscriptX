"""Native-host gate for G5 capture controls."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.services.capture import host_control
from transcriptx.services.capture.host_control import capture_controls_available


@pytest.mark.unit
def test_capture_hidden_off_darwin(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        "transcriptx.services.capture.host_control.detect_in_container",
        lambda: False,
    )
    assert capture_controls_available() is False


@pytest.mark.unit
def test_capture_hidden_in_container(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        "transcriptx.services.capture.host_control.detect_in_container",
        lambda: True,
    )
    monkeypatch.setattr(
        "transcriptx.services.capture.host_control.capture_script_path",
        lambda: Path("/tmp/system-audio-capture.py"),
    )
    assert capture_controls_available() is False


@pytest.mark.unit
def test_capture_visible_on_native_mac(monkeypatch, tmp_path):
    script = tmp_path / "system-audio-capture.py"
    script.write_text("#", encoding="utf-8")
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        "transcriptx.services.capture.host_control.detect_in_container",
        lambda: False,
    )
    monkeypatch.setattr(
        "transcriptx.services.capture.host_control.capture_script_path",
        lambda: script,
    )
    assert capture_controls_available() is True


@pytest.mark.unit
def test_start_spawns_host_script(monkeypatch, tmp_path):
    script = tmp_path / "system-audio-capture.py"
    script.write_text("#", encoding="utf-8")
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = list(cmd)
        return SimpleNamespace(returncode=0, stdout="recording\n", stderr="")

    monkeypatch.setattr(host_control, "capture_script_path", lambda: script)
    monkeypatch.setattr(host_control.subprocess, "run", fake_run)
    result = host_control.start_capture(title="supervision", mix_mic=True)
    assert result.returncode == 0
    assert seen["cmd"][1] == str(script)
    assert "start" in seen["cmd"]
    assert seen["cmd"][seen["cmd"].index("--name") + 1] == "supervision"
    assert "--mix-mic" in seen["cmd"]
    assert not any(part.endswith("ffmpeg") for part in seen["cmd"])
