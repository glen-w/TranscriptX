"""Tests for natural-language rename title helpers."""

from __future__ import annotations

import pytest

from transcriptx.core.utils.rename.title_stem import (
    is_generic_device_filename_stem,
    propose_dated_title,
    split_title_tokens,
    stem_looks_like_natural_language_title,
    underscore_title,
)


@pytest.mark.unit
def test_split_camel_case_title() -> None:
    stem = "OuroceanBeyondBordersUnderstandingtheHighSeasTreaty"
    assert split_title_tokens(stem) == [
        "Ourocean",
        "Beyond",
        "Borders",
        "Understandingthe",
        "High",
        "Seas",
        "Treaty",
    ]


@pytest.mark.unit
def test_underscore_title_from_spaces() -> None:
    stem = "Our Ocean Beyond Borders"
    assert underscore_title(stem) == "Our_Ocean_Beyond_Borders"


@pytest.mark.unit
def test_propose_dated_title() -> None:
    stem = "Our Ocean Beyond Borders"
    assert propose_dated_title("260908_", stem) == "260908_Our_Ocean_Beyond_Borders"
    assert (
        propose_dated_title("260908_", "260908_already_dated")
        == "260908_already_dated"
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "stem",
    [
        "R20260810-173237",
        "VOICE001",
        "ZOOM0002",
        "TASCAM_0001",
        "20260810120000",
    ],
)
def test_generic_device_stems(stem: str) -> None:
    assert is_generic_device_filename_stem(stem)
    assert not stem_looks_like_natural_language_title(stem)


@pytest.mark.unit
def test_natural_language_title_stem() -> None:
    stem = "Our Ocean Beyond Borders Understanding the High Seas Treaty"
    assert not is_generic_device_filename_stem(stem)
    assert stem_looks_like_natural_language_title(stem)


@pytest.mark.unit
def test_short_stem_not_natural_language() -> None:
    assert not stem_looks_like_natural_language_title("notes")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("token", "case", "expected"),
    [
        ("RATIFIED", "upper", "RATIFIED"),
        ("RATIFIED", "lower", "ratified"),
        ("RATIFIED", "title", "Ratified"),
        ("evening", "upper", "EVENING"),
        ("BBNJ", "title", "Bbnj"),
    ],
)
def test_format_bubble_token(token: str, case: str, expected: str) -> None:
    from transcriptx.core.utils.rename.title_stem import format_bubble_token

    assert format_bubble_token(token, case) == expected


@pytest.mark.unit
def test_format_rename_stem_case() -> None:
    from transcriptx.core.utils.rename.title_stem import format_rename_stem_case

    stem = "260908_Our_Ocean_Beyond"
    assert format_rename_stem_case(stem, "upper") == "260908_OUR_OCEAN_BEYOND"
    assert format_rename_stem_case(stem, "lower") == "260908_our_ocean_beyond"
    assert format_rename_stem_case("RATIFIED_NOW", "title") == "Ratified_Now"
