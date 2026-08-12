"""Accessible adjacent ⓘ tooltip helpers for non-widget labels and headings.

Streamlit widgets should prefer the built-in ``help=`` parameter (native ⓘ).
Use this module when help must sit beside a markdown heading, metric label,
or other non-widget touchpoint.
"""

from __future__ import annotations

import html
from collections.abc import Sequence


def build_info_tooltip_html(
    lines: Sequence[str] | str,
    *,
    control_id: str,
    aria_label: str,
    test_id: str = "tx-info-tooltip",
    tip_extra_class: str = "tx-methodology-info-tip",
    wrap_extra_class: str = "tx-methodology-info",
) -> str:
    """Build an ⓘ button + tooltip for one or more help lines.

    Returns an empty string when there is no tip body.
    """
    if isinstance(lines, str):
        body_lines = [lines] if lines.strip() else []
    else:
        body_lines = [str(line) for line in lines if str(line).strip()]
    if not body_lines:
        return ""
    tip_body = "<br>".join(html.escape(line) for line in body_lines)
    tip_id = html.escape(control_id, quote=True)
    aria = html.escape(aria_label, quote=True)
    test = html.escape(test_id, quote=True)
    wrap_cls = html.escape(
        f"tx-run-id-info {wrap_extra_class}".strip(), quote=True
    )
    tip_cls = html.escape(
        f"tx-run-id-info-tip {tip_extra_class}".strip(), quote=True
    )
    return (
        f'<span class="{wrap_cls}" data-testid="{test}">'
        f'<button type="button" class="tx-run-id-info-btn" tabindex="0" '
        f'aria-label="{aria}" aria-describedby="{tip_id}">ⓘ</button>'
        f'<span id="{tip_id}" class="{tip_cls}" role="tooltip">{tip_body}</span>'
        f"</span>"
    )


def build_section_heading_with_info_html(
    title: str,
    tip_html: str,
    *,
    heading_tag: str = "h4",
) -> str:
    """Wrap a section title and optional ⓘ tip in the shared heading flex row."""
    tag = heading_tag if heading_tag in {"h3", "h4", "h5", "h6"} else "h4"
    return (
        f'<div class="tx-section-info-heading">'
        f"<{tag}>{html.escape(title)}</{tag}>"
        f"{tip_html}"
        f"</div>"
    )
