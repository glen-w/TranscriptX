"""Unit tests for non-neutral emotion-family chart helpers."""

from __future__ import annotations

from copy import deepcopy

import pytest

from transcriptx.core.analysis.emotion_family.errors import NonNeutralChartInputError
from transcriptx.core.analysis.emotion_family.non_neutral_charts import (
    build_non_neutral_bar_series,
    iter_named_speaker_label_counts,
)


@pytest.mark.unit
def test_build_non_neutral_alpha_mixed_and_immutability() -> None:
    counts = {"joy": 3, "anger": 1, "neutral": 100, "sadness": 0}
    before = deepcopy(counts)
    series = build_non_neutral_bar_series(counts, order="alpha")
    assert counts == before
    assert series is not None
    assert series.categories == ("anger", "joy")
    assert series.counts == (1.0, 3.0)
    assert series.shares == pytest.approx((0.25, 0.75))
    assert series.non_neutral_total == 4.0
    assert sum(series.shares) == pytest.approx(1.0)


@pytest.mark.unit
def test_build_non_neutral_case_insensitive_neutral_and_missing_neutral() -> None:
    series = build_non_neutral_bar_series(
        {"JOY": 2, "Neutral": 9, "anger": 2},
        order="alpha",
    )
    assert series is not None
    assert series.categories == ("JOY", "anger")
    assert "Neutral" not in series.categories

    missing = build_non_neutral_bar_series({"joy": 1, "fear": 1}, order="alpha")
    assert missing is not None
    assert missing.categories == ("fear", "joy")


@pytest.mark.unit
def test_build_non_neutral_empty_all_neutral_and_zero_only() -> None:
    assert build_non_neutral_bar_series({}, order="alpha") is None
    assert build_non_neutral_bar_series({"neutral": 12}, order="alpha") is None
    assert build_non_neutral_bar_series({"NEUTRAL": 3}, order="top_n") is None
    assert (
        build_non_neutral_bar_series(
            {"joy": 0, "anger": 0, "neutral": 5}, order="alpha"
        )
        is None
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad",
    [
        {"joy": -1},
        {"joy": float("nan")},
        {"joy": float("inf")},
        {"joy": True},
        {"joy": "3"},
        {"joy": None},
    ],
)
def test_build_non_neutral_fail_closed_on_invalid(bad: dict) -> None:
    with pytest.raises(NonNeutralChartInputError):
        build_non_neutral_bar_series(bad, order="alpha")


@pytest.mark.unit
@pytest.mark.parametrize("top_n", [0, -1, True, 1.5, "15"])
def test_build_non_neutral_rejects_invalid_top_n(top_n: object) -> None:
    with pytest.raises(NonNeutralChartInputError):
        build_non_neutral_bar_series({"joy": 1}, order="top_n", top_n=top_n)  # type: ignore[arg-type]


@pytest.mark.unit
def test_build_non_neutral_top_n_full_denominator_and_tie_break() -> None:
    counts = {"neutral": 999}
    high = [
        "admiration",
        "amusement",
        "anger",
        "annoyance",
        "approval",
        "caring",
        "confusion",
        "curiosity",
        "desire",
        "disappointment",
        "disapproval",
        "disgust",
        "embarrassment",
        "excitement",
    ]
    for i, name in enumerate(high):
        counts[name] = 30 - i
    counts["fear"] = 5
    counts["grief"] = 5  # tied with fear; alpha prefers fear for the 15th slot
    counts["gratitude"] = 4

    series = build_non_neutral_bar_series(counts, order="top_n", top_n=15)
    assert series is not None
    assert list(series.categories) == high + ["fear"]
    assert "grief" not in series.categories
    assert "gratitude" not in series.categories
    assert "neutral" not in series.categories

    non_neutral_total = sum(v for k, v in counts.items() if k != "neutral")
    assert series.non_neutral_total == float(non_neutral_total)
    assert sum(series.shares) < 1.0 - 1e-9
    assert series.shares[-1] == pytest.approx(5.0 / non_neutral_total)
    assert series.counts == tuple(counts[c] for c in series.categories)


@pytest.mark.unit
def test_iter_named_speaker_label_counts_filters_unnamed_and_empty() -> None:
    pairs = iter_named_speaker_label_counts(
        {
            "Alice": {"label_counts": {"joy": 1}},
            "SPEAKER_00": {"label_counts": {"joy": 2}},
            "Bob": {"label_counts": {}},
            "Carol": {"label_counts": {"anger": 1}},
        }
    )
    assert [s for s, _ in pairs] == ["Alice", "Carol"]
