"""Secret redaction helpers for transcription subprocess output."""

from __future__ import annotations

from typing import Sequence


def redact_secret(text: str, secrets: Sequence[str]) -> str:
    """Replace any non-empty secret substring with '***'."""
    result = text
    for secret in secrets:
        if secret:
            result = result.replace(secret, "***")
    return result


def tail_lines(text: str, *, max_lines: int = 20) -> tuple[str, ...]:
    """Return the last *max_lines* non-empty lines as an immutable tuple."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return tuple(lines[-max_lines:])
