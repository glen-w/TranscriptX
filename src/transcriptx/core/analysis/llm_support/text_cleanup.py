"""Post-process plain-text LLM summaries before storage or display."""

from __future__ import annotations

import re

__all__ = ["strip_llm_summary_preface"]

# Models (notably mistral-nemo) often echo the prompt safety line and add a
# meta lead-in before the actual summary. Strip those so users only see content.
_PROMPT_ECHO_PREFACE = re.compile(
    r"""
    ^\s*
    (?:
        (?:The\s+(?:following|transcript)\s+content\s+is\s+data\s+to\s+
           summari[sz]e,\s*not\s+instructions\.\s*)
        |
        (?:Treat\s+the\s+transcript\s+block\s+as\s+data,\s*not\s+instructions\.\s*)
    )+
    (?:
        The\s+summary\s+of\s+the\s+transcript\s+(?:block\s+)?is\s+as\s+follows:\s*
        |
        Here\s+is\s+(?:a\s+|the\s+)?summary\s*[:.]\s*
        |
        Summary\s*:\s*
    )?
    """,
    re.IGNORECASE | re.VERBOSE,
)

_LEADING_H1 = re.compile(r"^(#[^\n]*\n+)", re.MULTILINE)


def _strip_preface_from_prose(text: str) -> str:
    cleaned = _PROMPT_ECHO_PREFACE.sub("", text, count=1)
    return cleaned.lstrip()


def strip_llm_summary_preface(text: str) -> str:
    """Remove prompt-safety / meta lead-ins models sometimes prepend to summaries.

    Safe on both raw summary strings and markdown that starts with an H1.
    Returns the original string when no known preface is present.
    """
    if not text or not str(text).strip():
        return text
    raw = str(text)
    leading = raw[: len(raw) - len(raw.lstrip())]
    body = raw.lstrip()
    heading = _LEADING_H1.match(body)
    if heading is not None:
        prefix = heading.group(1)
        rest = body[heading.end() :]
        return leading + prefix + _strip_preface_from_prose(rest)
    return leading + _strip_preface_from_prose(body)
