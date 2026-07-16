"""Layout width helper contracts."""

from __future__ import annotations

from transcriptx.web import layout
from transcriptx.web.navigation import PAGE_SPECS


def test_wide_pages_are_registered_in_page_specs():
    layout.assert_wide_pages_registered()
    keys = {spec.key for spec in PAGE_SPECS}
    for page in layout.WIDE_PAGE_KEYS:
        assert page in keys


def test_page_uses_wide_layout():
    assert layout.page_uses_wide_layout("Charts") is True
    assert layout.page_uses_wide_layout("Transcript") is True
    assert layout.page_uses_wide_layout("Artifacts") is True
    assert layout.page_uses_wide_layout("Home") is True
    assert layout.page_uses_wide_layout("Library") is False
    assert layout.page_uses_wide_layout("Statistics") is False
    assert layout.page_uses_wide_layout(None) is False


def test_apply_page_layout_injects_complete_rule_each_call(monkeypatch):
    calls: list[str] = []

    class _FakeSt:
        @staticmethod
        def markdown(body, **_kwargs):
            calls.append(body)

    monkeypatch.setattr(layout, "st", _FakeSt)
    layout.apply_page_layout(wide=True)
    layout.apply_page_layout(wide=False)
    assert len(calls) == 2
    assert "tx-page-layout: wide" in calls[0]
    assert "max-width: min(100%, 1600px)" in calls[0]
    assert "tx-page-layout: constrained" in calls[1]
    assert "max-width: 1240px" in calls[1]
    # Complete rules, not partial leftovers
    assert calls[0].count("block-container") >= 1
    assert calls[1].count("block-container") >= 1


def test_only_layout_module_owns_width_css():
    from pathlib import Path

    web = Path(__file__).resolve().parents[2] / "src" / "transcriptx" / "web"
    offenders = []
    for path in web.rglob("*.py"):
        if path.name == "layout.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "tx-page-layout" in text and "apply_page_layout" not in text:
            offenders.append(path.name)
        if "max-width: 1240px" in text:
            offenders.append(path.name)
    assert offenders == []
