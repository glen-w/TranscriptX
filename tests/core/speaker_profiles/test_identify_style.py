"""Style vector open-set ranking."""

from __future__ import annotations

import pytest

from transcriptx.core.speaker_profiles.identify.style import (
    STYLE_STRONG_MIN,
    build_style_vector,
    rank_style_open_set,
    style_similarity,
)


def _pad(text: str, n: int = 20) -> list[str]:
    return [text] * n


@pytest.mark.unit
def test_identical_style_is_high() -> None:
    vector = build_style_vector(_pad("I think we should actually just do the plan."))
    assert vector is not None
    assert style_similarity(vector, vector) > 0.99


@pytest.mark.unit
def test_rank_requires_unique_strong_winner() -> None:
    query = build_style_vector(
        _pad("Well I just really think we should actually do this now.")
    )
    close = build_style_vector(
        _pad("Well I just really think we should actually do that now.")
    )
    other = build_style_vector(_pad("The cat sat on the mat and then ran away quickly."))
    assert query and close and other
    none = rank_style_open_set(
        query, {"p1": close, "p2": close}, names={"p1": "A", "p2": "B"}
    )
    assert none is None
    winner = rank_style_open_set(
        query, {"p1": query, "p2": other}, names={"p1": "Maya", "p2": "Sam"}
    )
    assert winner is not None
    assert winner.profile_id == "p1"
    assert winner.display_name == "Maya"
    assert winner.confidence == "strong"
    assert (winner.score or 0) >= STYLE_STRONG_MIN
