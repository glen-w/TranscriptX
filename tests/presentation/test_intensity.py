"""Tests for intensity helpers."""

from __future__ import annotations

import pytest

from transcriptx.core.presentation.intensity import bucket, render_intensity_line


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, "unknown"),
        (0.1, "low"),
        (0.5, "medium"),
        (0.9, "high"),
    ],
)
def test_bucket(value: float | None, expected: str) -> None:
    assert bucket(value) == expected


def test_render_intensity_line() -> None:
    line = render_intensity_line("Highlights", 0.25)
    assert line.startswith("**Highlights intensity:**")
    assert "(0.25)" in line
