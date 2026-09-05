"""
Tests for transcript tag validation utilities.
"""

from __future__ import annotations

import pytest

from transcriptx.io.tag_validation import (
    KNOWN_SEMANTIC_TAGS,
    build_tag_details,
    normalize_tag,
    sanitize_tag,
    sanitize_tag_list,
    validate_tag,
    validate_tag_details,
)


class TestNormalizeTag:
    def test_strips_and_lowercases(self) -> None:
        assert normalize_tag("  Meeting  ") == "meeting"

    def test_collapses_whitespace(self) -> None:
        assert normalize_tag("voice   note") == "voice note"


class TestValidateTag:
    @pytest.mark.parametrize(
        "raw",
        ["meeting", "voice note", "team-sync", "q1_review", "a"],
    )
    def test_accepts_valid_tags(self, raw: str) -> None:
        is_valid, err = validate_tag(raw)
        assert is_valid, err

    @pytest.mark.parametrize(
        "raw,fragment",
        [
            ("", "empty"),
            ("   ", "empty"),
            ("../escape", "invalid"),
            ("tag/path", "invalid"),
            ("-leading-hyphen", "start"),
            ("trailing-", "end"),
            ("x" * 65, "too long"),
            ("tag\x00bad", "control"),
        ],
    )
    def test_rejects_invalid_tags(self, raw: str, fragment: str) -> None:
        is_valid, err = validate_tag(raw)
        assert not is_valid
        assert err is not None


class TestSanitizeTag:
    def test_returns_normalized_valid_tag(self) -> None:
        assert sanitize_tag("  Meeting ") == "meeting"

    def test_returns_none_for_invalid(self) -> None:
        assert sanitize_tag("../bad") is None


class TestSanitizeTagList:
    def test_deduplicates_case_insensitive(self) -> None:
        result = sanitize_tag_list(["Meeting", "meeting", "TODO"])
        assert result == ["meeting", "todo"]

    def test_drops_invalid_entries(self) -> None:
        result = sanitize_tag_list(["good", "../bad", "also-good"])
        assert result == ["good", "also-good"]

    def test_empty_input(self) -> None:
        assert sanitize_tag_list([]) == []
        assert sanitize_tag_list(None) == []


class TestValidateTagDetails:
    def test_valid_details(self) -> None:
        details = {
            "meeting": {"confidence": 0.9, "source": "auto"},
            "custom": {"confidence": 1.0, "source": "manual"},
        }
        is_valid, errors = validate_tag_details(details)
        assert is_valid
        assert errors == []

    def test_rejects_non_dict_root(self) -> None:
        is_valid, errors = validate_tag_details(["meeting"])
        assert not is_valid
        assert any("dictionary" in e for e in errors)

    def test_rejects_bad_confidence(self) -> None:
        is_valid, errors = validate_tag_details(
            {"meeting": {"confidence": 1.5, "source": "auto"}}
        )
        assert not is_valid
        assert any("confidence" in e for e in errors)

    def test_rejects_bad_source(self) -> None:
        is_valid, errors = validate_tag_details(
            {"meeting": {"confidence": 0.5, "source": "unknown"}}
        )
        assert not is_valid
        assert any("source" in e for e in errors)

    def test_cross_check_missing_detail(self) -> None:
        is_valid, errors = validate_tag_details(
            {"meeting": {"confidence": 0.9, "source": "auto"}},
            tags=["meeting", "todo"],
        )
        assert not is_valid
        assert any("missing from tag_details" in e for e in errors)


class TestBuildTagDetails:
    def test_marks_auto_and_manual_sources(self) -> None:
        details = build_tag_details(
            ["meeting", "custom"],
            auto_tags=["meeting"],
            existing_details={"meeting": {"confidence": 0.82, "indicators": ["kw"]}},
        )
        assert details["meeting"]["source"] == "auto"
        assert details["meeting"]["confidence"] == 0.82
        assert details["custom"]["source"] == "manual"
        assert details["custom"]["confidence"] == 1.0


class TestKnownSemanticTags:
    def test_includes_extraction_tags(self) -> None:
        assert KNOWN_SEMANTIC_TAGS == {
            "idea",
            "reflection",
            "meeting",
            "todo",
            "question",
        }
