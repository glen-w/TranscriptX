"""Unit tests for tertiary action-link helpers."""

from __future__ import annotations

from transcriptx.web.components import action_links


def test_action_link_key_prefixes_once():
    assert action_links.action_link_key("home_run") == "tx_al_home_run"
    assert action_links.action_link_key("tx_al_already") == "tx_al_already"


def test_render_action_link_forwards_to_streamlit_button(monkeypatch):
    captured: dict = {}

    class _FakeSt:
        @staticmethod
        def button(label, **kwargs):
            captured["label"] = label
            captured.update(kwargs)
            return True

    monkeypatch.setattr(action_links, "st", _FakeSt)
    clicked = []

    def _on_click(page: str) -> None:
        clicked.append(page)

    assert (
        action_links.render_action_link(
            "Open Charts",
            key="home_run_ch_1",
            icon=":material/bar_chart:",
            on_click=_on_click,
            args=("Charts",),
            help="Go to charts",
        )
        is True
    )
    assert captured["label"] == "Open Charts"
    assert captured["key"] == "tx_al_home_run_ch_1"
    assert captured["type"] == "tertiary"
    assert captured["width"] == "content"
    assert captured["icon"] == ":material/bar_chart:"
    assert captured["args"] == ("Charts",)
    assert captured["help"] == "Go to charts"
    assert captured["disabled"] is False
    captured["on_click"]("Charts")
    assert clicked == ["Charts"]


def test_render_download_link_forwards_to_streamlit_download_button(monkeypatch):
    captured: dict = {}

    class _FakeSt:
        @staticmethod
        def download_button(label, **kwargs):
            captured["label"] = label
            captured.update(kwargs)
            return True

    monkeypatch.setattr(action_links, "st", _FakeSt)
    assert (
        action_links.render_download_link(
            "TXT",
            data=b"hello",
            file_name="demo.txt",
            key="download_txt",
            mime="text/plain",
            help="Download transcript text",
        )
        is True
    )
    assert captured["label"] == "TXT"
    assert captured["key"] == "tx_al_download_txt"
    assert captured["type"] == "tertiary"
    assert captured["width"] == "content"
    assert captured["icon"] == ":material/download:"
    assert captured["file_name"] == "demo.txt"
    assert captured["mime"] == "text/plain"
    assert captured["data"] == b"hello"
    assert captured["help"] == "Download transcript text"
    assert captured["disabled"] is False
