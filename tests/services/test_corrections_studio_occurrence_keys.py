"""Regression tests for Corrections Studio stable occurrence keys."""

from __future__ import annotations

import hashlib

import pytest

from transcriptx.services.corrections_studio.occurrence_keys import (
    stable_occurrence_key,
)


def _pre_extraction_stable_occurrence_key(
    segment_id: str, span_start: int, span_end: int, wrong_text: str
) -> str:
    """Recipe duplicated from pre-refactor candidate_service / normalize (parity guard)."""
    sig = f"{segment_id}:{span_start}:{span_end}:{wrong_text}"
    return hashlib.sha1(sig.encode("utf-8")).hexdigest()


@pytest.mark.unit
def test_stable_occurrence_key_matches_pre_extraction_recipe() -> None:
    assert stable_occurrence_key(
        "s0", 1, 5, "typo"
    ) == _pre_extraction_stable_occurrence_key("s0", 1, 5, "typo")


@pytest.mark.unit
def test_stable_occurrence_key_golden_digest() -> None:
    assert (
        stable_occurrence_key("seg-a", 0, 3, "foo")
        == "d4f35680e5c0eb52ce41d9ff8ab09582fc2e1bc1"
    )


@pytest.mark.unit
def test_stable_occurrence_key_empty_wrong_text() -> None:
    sig = "s:-1:-1:"
    expected = hashlib.sha1(sig.encode("utf-8")).hexdigest()
    assert stable_occurrence_key("s", -1, -1, "") == expected


@pytest.mark.unit
def test_stable_occurrence_key_unicode_matches_utf8_recipe() -> None:
    seg = "セグ"
    wrong = "naïve"
    a, b = 0, 4
    assert (
        stable_occurrence_key(seg, a, b, wrong)
        == hashlib.sha1(f"{seg}:{a}:{b}:{wrong}".encode("utf-8")).hexdigest()
    )
