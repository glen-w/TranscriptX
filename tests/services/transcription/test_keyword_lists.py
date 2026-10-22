"""Tests for saved STT keyword lists."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.services.transcription.keyword_lists import (
    MAX_KEYWORDS,
    KeywordListError,
    delete_list,
    export_list_json,
    import_list,
    list_lists,
    load_list,
    normalize_keywords,
    parse_keyword_text,
    resolve_run_keywords,
    save_list,
)


@pytest.mark.unit
def test_normalize_strips_dedupes_and_caps() -> None:
    terms, warning = normalize_keywords(
        [" NATO ", "NATO", "", "FY26", None, "  "],
        cap=3,
    )
    assert terms == ("NATO", "FY26")
    assert warning is None
    huge = [f"k{i}" for i in range(MAX_KEYWORDS + 5)]
    capped, warning = normalize_keywords(huge)
    assert len(capped) == MAX_KEYWORDS
    assert warning is not None
    assert "2000" in warning


@pytest.mark.unit
def test_parse_keyword_text_lines_commas_and_json() -> None:
    assert parse_keyword_text("AAA\nBBB, CCC") == ["AAA", "BBB", "CCC"]
    assert parse_keyword_text('["X", "Y"]') == ["X", "Y"]
    assert parse_keyword_text('{"keywords": ["Z"]}') == ["Z"]


@pytest.mark.unit
def test_save_load_list_roundtrip(tmp_path: Path) -> None:
    assert save_list("acronyms", ["NATO", "FY26"], profiles_dir=tmp_path)
    assert list_lists(profiles_dir=tmp_path) == ["acronyms"]
    assert load_list("acronyms", profiles_dir=tmp_path) == ("NATO", "FY26")
    payload = export_list_json("acronyms", profiles_dir=tmp_path)
    assert "NATO" in payload
    assert delete_list("acronyms", profiles_dir=tmp_path) is True
    with pytest.raises(KeywordListError):
        load_list("acronyms", profiles_dir=tmp_path)


@pytest.mark.unit
def test_import_list_from_txt(tmp_path: Path) -> None:
    terms = import_list("imported", "FOO\nBAR\n", profiles_dir=tmp_path)
    assert terms == ("FOO", "BAR")


@pytest.mark.unit
def test_resolve_run_keywords_default_off(tmp_path: Path) -> None:
    save_list("acronyms", ["NATO"], profiles_dir=tmp_path)
    keywords, warning = resolve_run_keywords(
        enabled=False, list_name="acronyms", extra="FY26", profiles_dir=tmp_path
    )
    assert keywords == ()
    assert warning is None
    keywords, _warning = resolve_run_keywords(
        enabled=True, list_name="acronyms", extra="FY26", profiles_dir=tmp_path
    )
    assert keywords == ("NATO", "FY26")
