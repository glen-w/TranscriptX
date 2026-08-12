"""Tests for speaker Trends methodology info tooltip."""

from __future__ import annotations

from transcriptx.web.page_modules import speakers


def test_methodology_lines_skip_partners():
    lines = speakers._methodology_lines(
        [
            "grain.appearance_date",
            "pack.phase16",
            "partners.co_appearance_only",
            "share.duration_only",
        ]
    )
    assert lines == [
        "Grouped by appearance date.",
        "Trends are derived from confirmed profile links; not persisted as canonical data.",
        "Speaking share uses duration only (never turn share).",
    ]


def test_methodology_info_html_escapes_and_is_accessible(monkeypatch):
    monkeypatch.setattr(
        "transcriptx.web.components.info_tooltip.info_tooltips_enabled",
        lambda: True,
    )
    html_out = speakers._methodology_info_html(
        ["Grouped by appearance date.", 'Line with <script>"x"'],
        control_id="spk-meth-1",
    )
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out
    assert 'tabindex="0"' in html_out
    assert 'role="tooltip"' in html_out
    assert 'id="spk-meth-1"' in html_out
    assert "tx-methodology-info" in html_out
    assert "tx-methodology-info-tip" in html_out
    assert "Grouped by appearance date." in html_out
    assert "<br>" in html_out
    assert html_out.count("<br>") == 1


def test_methodology_info_html_empty_when_no_lines(monkeypatch):
    monkeypatch.setattr(
        "transcriptx.web.components.info_tooltip.info_tooltips_enabled",
        lambda: True,
    )
    assert speakers._methodology_info_html([], control_id="x") == ""


def test_methodology_info_html_suppressed_when_tips_disabled(monkeypatch):
    monkeypatch.setattr(
        "transcriptx.web.components.info_tooltip.info_tooltips_enabled",
        lambda: False,
    )
    assert (
        speakers._methodology_info_html(
            ["Grouped by appearance date."],
            control_id="spk-meth-off",
        )
        == ""
    )


def test_partners_info_tooltip_is_methodology_only(monkeypatch):
    monkeypatch.setattr(
        "transcriptx.web.components.info_tooltip.info_tooltips_enabled",
        lambda: True,
    )
    html_out = speakers._info_tooltip_html(
        [
            "Partners are co-appearances in shared sessions, not interaction proof.",
        ],
        control_id="spk-partners-1",
        aria_label="Conversation partners notes",
        test_id="tx-partners-info",
    )
    assert 'data-testid="tx-partners-info"' in html_out
    assert "Partners are co-appearances" in html_out
    assert "Conversation partners notes" in html_out
    assert "duplicate_live_link" not in html_out
    assert "merged_owner_link" not in html_out


def test_section_heading_with_info_escapes_title(monkeypatch):
    monkeypatch.setattr(
        "transcriptx.web.components.info_tooltip.info_tooltips_enabled",
        lambda: True,
    )
    tip = speakers._info_tooltip_html(
        ["note"],
        control_id="t1",
        aria_label="Notes",
    )
    html_out = speakers._section_heading_with_info_html("Partners <script>", tip)
    assert "<script>" not in html_out
    assert "Partners &lt;script&gt;" in html_out
    assert "tx-section-info-heading" in html_out
    assert tip in html_out
