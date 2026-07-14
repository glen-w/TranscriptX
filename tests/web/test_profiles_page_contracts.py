"""Tests for profiles page contracts."""

from __future__ import annotations

from transcriptx.web.page_modules.profiles import (
    _create_copy_options,
    _split_profile_names_for_display,
)


def test_split_profile_names_places_default_in_baseline_only() -> None:
    baseline, saved = _split_profile_names_for_display(["default", "a", "b"])
    assert baseline == ["default"]
    assert saved == ["a", "b"]


def test_split_profile_names_without_default() -> None:
    baseline, saved = _split_profile_names_for_display(["a", "b"])
    assert baseline == []
    assert saved == ["a", "b"]


def test_create_copy_options_fallback_to_default() -> None:
    assert _create_copy_options([]) == ["default"]


def test_create_copy_options_uses_saved_profiles() -> None:
    assert _create_copy_options(["x", "y"]) == ["x", "y"]
