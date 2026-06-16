"""
Streamlit-friendly labels for module pickers (avoids circular imports with module_ui_groups).
"""

from __future__ import annotations

from collections.abc import Callable

from transcriptx.web.module_registry import build_module_label
from transcriptx.web.module_ui_groups import group_title_for_module_id


def format_module_option(
    module_id: str,
    *,
    label_builder: Callable[[str], str] | None = None,
) -> str:
    """
    Prefix group title, then module label for known spec modules;
    unknown ids use "Other · …".

    Values passed to multiselect/selectbox should remain raw module_id strings.
    """
    lb = label_builder if label_builder is not None else build_module_label
    label = lb(module_id)
    title = group_title_for_module_id(module_id)
    if title:
        return f"{title} · {label}"
    return f"Other · {label}"
