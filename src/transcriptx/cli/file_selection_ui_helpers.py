"""
UI helper functions for the file selection interface.

This module provides utility functions for building UI components
like help text and headers.
"""

import shutil
from typing import List, Tuple

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import FormattedTextControl
from prompt_toolkit.utils import get_cwidth


def build_help_text(
    shortcuts: List[Tuple[str, str, str]], box_width: int | None = None
) -> FormattedTextControl:
    """
    Build formatted help text with keyboard shortcuts in a box layout.

    Args:
        shortcuts: List of (emoji, action, key) tuples
        box_width: Width of the help text box. If None, auto-fit terminal width.

    Returns:
        FormattedTextControl with the help text
    """
    def truncate_to_width(text: str, max_width: int) -> str:
        """Truncate text by display width (handles wide unicode)."""
        if max_width <= 0:
            return ""
        if get_cwidth(text) <= max_width:
            return text
        # Reserve 3 cols for "..." when possible
        if max_width <= 3:
            # Best-effort hard cut; still display-width safe for small max_width.
            out = ""
            for ch in text:
                if get_cwidth(out + ch) > max_width:
                    break
                out += ch
            return out
        out = ""
        for ch in text:
            if get_cwidth(out + ch) > max_width - 3:
                break
            out += ch
        return out + "..."

    # Auto-fit width to avoid prompt_toolkit truncation.
    terminal_cols = shutil.get_terminal_size(fallback=(120, 24)).columns
    # Keep a small margin to avoid line-wrapping/truncation in some terminals.
    max_box_width = max(20, terminal_cols - 4)
    desired_width = box_width if box_width is not None else max_box_width
    box_width = max(20, min(desired_width, max_box_width))

    # Use 2 columns to keep height compact (callers often reserve limited space).
    num_columns = 2
    items_per_column = (len(shortcuts) + num_columns - 1) // num_columns

    # Build boxed help text
    help_lines = []
    help_lines.append("┌" + "─" * box_width + "┐")

    # Calculate available width for content (box_width minus borders and padding).
    # We render each line as: "│  " + content + "  │"
    available_width = box_width - 6

    # Calculate separator: "  │  " is 5 characters
    separator = "  │  "
    separator_width = len(separator)

    # Calculate column width (account for separator)
    column_width = (available_width - separator_width) // 2
    column_width = max(12, column_width)

    # Group shortcuts into columns with proper spacing and alignment
    for row in range(items_per_column):
        line_parts = []
        
        for col in range(num_columns):
            idx = col * items_per_column + row
            if idx < len(shortcuts):
                emoji, action, key = shortcuts[idx]
                # Prefer keeping key visible; truncate action first.
                emoji_prefix = f"{emoji}  "
                emoji_w = get_cwidth(emoji_prefix)
                key_w = get_cwidth(key)

                # If key itself doesn't fit, truncate key (rare; extremely narrow terminals).
                if emoji_w + 2 + key_w > column_width:
                    key_fit = max(0, column_width - emoji_w - 2)
                    key_display = truncate_to_width(key, key_fit)
                    item = f"{emoji_prefix}{key_display}"
                else:
                    action_width = max(0, column_width - emoji_w - 2 - key_w)
                    action_display = truncate_to_width(action, action_width)
                    # Pad action to keep keys aligned.
                    action_pad = " " * max(0, action_width - get_cwidth(action_display))
                    item = f"{emoji_prefix}{action_display}{action_pad}  {key}"
            else:
                item = ""
            
            # Pad item to column width
            pad = max(0, column_width - get_cwidth(item))
            item_padded = item + (" " * pad)
            line_parts.append(item_padded)
            
            # Add separator between columns (not after last)
            if col < num_columns - 1:
                line_parts.append(separator)

        # Join parts and ensure exact width
        content = "".join(line_parts)
        content_w = get_cwidth(content)
        if content_w < available_width:
            content = content + (" " * (available_width - content_w))
        elif content_w > available_width:
            content = truncate_to_width(content, available_width)
        
        help_lines.append("│  " + content + "  │")

    help_lines.append("└" + "─" * box_width + "┘")

    help_text_str = "\n".join(help_lines)
    return FormattedTextControl(FormattedText([("", help_text_str)]))


def build_header_text(
    title: str, current_path: str | None = None, file_count: int = 0
) -> FormattedText:
    """
    Build formatted header text for the file selection interface.

    Args:
        title: Title of the selection interface
        current_path: Current directory path (optional)
        file_count: Number of files found

    Returns:
        FormattedText with the header
    """
    header_parts = [
        ("", "\n"),
        ("bold cyan", title),
        ("", "\n"),
    ]
    if current_path:
        header_parts.extend(
            [
                ("fg:ansigray", f"Current location: {current_path}"),
                ("", "\n"),
            ]
        )
    header_parts.append(("green", f"Found {file_count} file(s)"))
    header_parts.append(("", "\n"))

    return FormattedText(header_parts)
