"""
Standardized no-signal messaging for Markdown outputs.
"""

from __future__ import annotations

from typing import List, Optional


def render_no_signal_md(
    reason: str,
    *,
    threshold: str | None = None,
    metric: str | None = None,
    looked_for: Optional[List[str]] = None,
) -> str:
    lines = ["## No strong signal detected", ""]
    if reason:
        lines.append(reason)
    if metric or threshold:
        metric_text = metric or "metric"
        threshold_text = threshold or "n/a"
        lines.append(f"Checked {metric_text} against threshold {threshold_text}.")
    if looked_for:
        lines.append("")
        lines.append("Looked for:")
        for item in looked_for:
            lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)
