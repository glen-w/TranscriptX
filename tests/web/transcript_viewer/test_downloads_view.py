"""Tests for downloads view."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import transcriptx.web.transcript_viewer.downloads as mod


@dataclass
class _Artifacts:
    txt_file: Path | None = None
    csv_file: Path | None = None
    srt_file: Path | None = None
    json_file: Path | None = None


class _DummyCol:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_render_download_row_fallback_json(monkeypatch) -> None:
    captured: list[dict] = []

    class _DummySt:
        @staticmethod
        def columns(spec, **_kwargs):
            return tuple(_DummyCol() for _ in range(int(spec)))

    def _capture_download_link(label, **kwargs):
        captured.append({"label": label, **kwargs})
        return False

    monkeypatch.setattr(mod, "st", _DummySt)
    monkeypatch.setattr(mod, "render_download_link", _capture_download_link)
    mod.render_download_row(_Artifacts(), {"segments": []}, "slug/run1")
    keys = {item.get("key") for item in captured}
    assert keys == {"download_json"}
    assert captured[0]["label"] == "JSON"
    assert captured[0]["icon"] == ":material/download:"
    assert captured[0]["file_name"] == "slug/run1_transcript.json"


def test_render_download_row_includes_srt_when_present(
    tmp_path: Path, monkeypatch
) -> None:
    captured: list[dict] = []
    srt_path = tmp_path / "demo-transcript.srt"
    srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n\n", encoding="utf-8")

    class _DummySt:
        @staticmethod
        def columns(spec, **_kwargs):
            return tuple(_DummyCol() for _ in range(int(spec)))

    def _capture_download_link(label, **kwargs):
        captured.append({"label": label, **kwargs})
        return False

    monkeypatch.setattr(mod, "st", _DummySt)
    monkeypatch.setattr(mod, "render_download_link", _capture_download_link)
    mod.render_download_row(
        _Artifacts(srt_file=srt_path),
        {"segments": []},
        "slug/run1",
    )
    srt_links = [item for item in captured if item.get("key") == "download_srt"]
    assert len(srt_links) == 1
    assert srt_links[0]["label"] == "SRT"
    assert srt_links[0]["file_name"] == "demo-transcript.srt"
    assert srt_links[0]["mime"] == "application/x-subrip"
    assert srt_links[0]["icon"] == ":material/download:"
    assert {item.get("key") for item in captured} == {"download_srt", "download_json"}
