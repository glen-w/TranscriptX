"""Dependency-light filename helpers for LLM artifacts.

Note: distinct speaker names can collide after sanitisation (e.g. ``"A B"``,
``"A_B"``, and ``"A/B"`` all map to ``"A_B"``). This behaviour is intentionally
preserved; collision-safe filename identity is tracked as separate work
because changing it would change artifact paths.
"""

from __future__ import annotations

__all__ = [
    "safe_speaker_filename",
]


def safe_speaker_filename(speaker: str) -> str:
    return str(speaker).replace(" ", "_").replace("/", "_")
