"""Tests for shared adjacent ⓘ tooltip HTML helpers."""

from __future__ import annotations

from transcriptx.web.components import info_tooltip


def test_build_info_tooltip_html_escapes_and_is_accessible() -> None:
    html_out = info_tooltip.build_info_tooltip_html(
        ['Line <b>one</b>', 'Line "two"'],
        control_id="tip-a",
        aria_label='Help for <section>',
        test_id="tx-info-tooltip",
    )
    assert "<b>one</b>" not in html_out
    assert "&lt;b&gt;one&lt;/b&gt;" in html_out
    assert 'tabindex="0"' in html_out
    assert 'role="tooltip"' in html_out
    assert 'id="tip-a"' in html_out
    assert "ⓘ" in html_out
    assert "aria-describedby" in html_out
    assert "Help for &lt;section&gt;" in html_out
    assert "tx-methodology-info" in html_out


def test_build_info_tooltip_html_empty_when_no_lines() -> None:
    assert info_tooltip.build_info_tooltip_html([], control_id="x", aria_label="a") == ""
    assert info_tooltip.build_info_tooltip_html("  ", control_id="x", aria_label="a") == ""


def test_build_section_heading_with_info_html() -> None:
    tip = info_tooltip.build_info_tooltip_html(
        "Note",
        control_id="t1",
        aria_label="Note",
    )
    heading = info_tooltip.build_section_heading_with_info_html("Trends", tip)
    assert 'class="tx-section-info-heading"' in heading
    assert "<h4>Trends</h4>" in heading
    assert "ⓘ" in heading
