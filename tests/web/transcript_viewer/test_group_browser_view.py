"""Tests for group browser view."""

from __future__ import annotations

from dataclasses import dataclass

from transcriptx.web.page_modules.transcript import _render_group_browser


@dataclass
class _Member:
    uuid: str | None = "u1"
    file_name: str | None = "name.json"
    file_path: str | None = "/tmp/name.json"


@dataclass
class _GroupSubject:
    members: list


class _DummySt:
    captions: list[str] = []
    subheaders: list[str] = []

    @classmethod
    def subheader(cls, text):
        cls.subheaders.append(text)

    @classmethod
    def info(cls, *_args, **_kwargs):
        return None

    @classmethod
    def caption(cls, text):
        cls.captions.append(text)

    @classmethod
    def button(cls, *_args, **_kwargs):
        return False

    class session_state(dict):
        pass

    @staticmethod
    def rerun():
        return None


def test_group_browser_renders_header(monkeypatch) -> None:
    monkeypatch.setattr("transcriptx.web.page_modules.transcript.st", _DummySt)
    monkeypatch.setattr(
        "transcriptx.web.page_modules.transcript.FileService.list_available_sessions",
        lambda: [],
    )
    monkeypatch.setattr(
        "transcriptx.web.page_modules.transcript.FileService.resolve_session_for_transcript_path",
        lambda _path, _sessions: None,
    )
    _render_group_browser(_GroupSubject(members=[_Member()]))
    assert "Group transcripts" in _DummySt.subheaders
    assert any("session not found" in c for c in _DummySt.captions)
