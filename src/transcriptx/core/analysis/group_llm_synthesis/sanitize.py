"""Sanitise error messages before UI/export exposure."""

from __future__ import annotations

import re

from transcriptx.core.analysis.group_llm_synthesis.schemas import SAFE_ERROR_MESSAGE_MAX

_PATH_RE = re.compile(r"(?:/Users/|/home/|/var/|/tmp/|[A-Za-z]:\\)[^\s\"']+")
_URL_RE = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)


def sanitise_error_message(
    message: str | None, *, max_len: int = SAFE_ERROR_MESSAGE_MAX
) -> str:
    text = str(message or "").strip()
    if not text:
        return ""
    text = _PATH_RE.sub("<path>", text)
    text = _URL_RE.sub("<endpoint>", text)
    text = text.replace("\n", " ").replace("\r", " ")
    if len(text) > max_len:
        text = text[: max_len - 3] + "..."
    return text
