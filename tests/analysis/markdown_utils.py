"""Markdown normalization for snapshot tests."""
from __future__ import annotations

import re


def normalize_markdown(md: str) -> str:
    text = md.replace("\r\n", "\n").rstrip() + "\n"
    # Remove trailing spaces on each line
    text = "\n".join([line.rstrip() for line in text.splitlines()]) + "\n"
    # Normalize multiple blank lines to max 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text
