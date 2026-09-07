"""Link-target ranking for Speaker Identification."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.speaker_profiles.aggregates import ProfileListItem
from transcriptx.services.speaker_profiles.link_targets import (
    resolve_save_link_mode,
    suggest_link_targets,
)


def _item(
    *,
    profile_id: str,
    name: str,
    status: str = "active",
    aliases: tuple[str, ...] = (),
    link_count: int = 2,
) -> ProfileListItem:
    return ProfileListItem(
        profile_id=profile_id,
        display_name=name,
        status=status,
        merged_into_profile_id=None,
        updated_at="2026-01-01T00:00:00+00:00",
        link_count=link_count,
        aliases=aliases,
        accent_color="#5B8DEF",
    )


@pytest.mark.unit
def test_unique_name_match_defaults_to_existing() -> None:
    listing = (_item(profile_id="p-maya", name="Maya"),)
    result = suggest_link_targets(
        display_name="maya",
        managed=True,
        listing=listing,
    )
    assert result.default_mode == "existing"
    assert result.default_profile_id == "p-maya"
    default = result.default_target()
    assert default is not None
    assert default.reason == "name_match"
    assert any(t.mode == "create" for t in result.targets)
    assert any(t.mode == "none" for t in result.targets)


@pytest.mark.unit
def test_alias_match_and_duplicate_create_warning() -> None:
    listing = (
        _item(profile_id="p1", name="Maya Chen", aliases=("Maya",)),
        _item(profile_id="p2", name="Jordan"),
    )
    result = suggest_link_targets(
        display_name="Maya",
        managed=True,
        listing=listing,
    )
    assert result.default_mode == "existing"
    assert result.default_profile_id == "p1"
    create = next(t for t in result.targets if t.mode == "create")
    assert create.duplicate_name_warning is False
    same = suggest_link_targets(
        display_name="Maya Chen",
        managed=True,
        listing=listing,
    )
    create_same = next(t for t in same.targets if t.mode == "create")
    assert create_same.duplicate_name_warning is True


@pytest.mark.unit
def test_ambiguous_name_does_not_auto_pick() -> None:
    listing = (
        _item(profile_id="p1", name="Sam"),
        _item(profile_id="p2", name="Sam"),
    )
    result = suggest_link_targets(
        display_name="Sam",
        managed=True,
        listing=listing,
    )
    assert result.default_mode == "create"
    assert result.default_profile_id is None
    assert sum(1 for t in result.targets if t.reason == "name_match") == 2


@pytest.mark.unit
def test_already_linked_wins_over_name_match() -> None:
    listing = (
        _item(profile_id="p-maya", name="Maya"),
        _item(profile_id="p-other", name="Jordan"),
    )
    live = SimpleNamespace(profile_id="p-other")
    result = suggest_link_targets(
        display_name="Maya",
        managed=True,
        listing=listing,
        live_link=live,  # type: ignore[arg-type]
    )
    assert result.default_mode == "existing"
    assert result.default_profile_id == "p-other"
    linked = result.default_target()
    assert linked is not None
    assert linked.already_linked is True
    assert linked.reason == "already_linked"


@pytest.mark.unit
def test_archived_excluded_and_unmanaged_is_name_only() -> None:
    listing = (
        _item(profile_id="p-old", name="Maya", status="archived"),
        _item(profile_id="p-live", name="Maya"),
    )
    archived_only = suggest_link_targets(
        display_name="Maya",
        managed=True,
        listing=(_item(profile_id="p-old", name="Maya", status="archived"),),
    )
    assert archived_only.default_mode == "create"
    assert all(t.reason != "name_match" for t in archived_only.targets)

    unmanaged = suggest_link_targets(
        display_name="Maya",
        managed=False,
        listing=listing,
    )
    assert unmanaged.default_mode == "none"
    assert unmanaged.recipe_hint
    assert not any(t.mode == "create" for t in unmanaged.targets)


@pytest.mark.unit
def test_voice_candidate_listed_but_not_default() -> None:
    listing = (_item(profile_id="p-voice", name="Jordan"),)
    result = suggest_link_targets(
        display_name="Maya",
        managed=True,
        listing=listing,
        voice_candidates=(
            {"profile_id": "p-voice", "display_name": "Jordan", "confidence": "strong"},
        ),
    )
    voice = next(t for t in result.targets if t.reason == "voice")
    assert voice.profile_id == "p-voice"
    assert result.default_mode == "create"


@pytest.mark.unit
def test_resolve_save_link_mode_compat_and_existing() -> None:
    assert resolve_save_link_mode({"link_profile": True}, profile_managed=True) == (
        "create",
        None,
    )
    assert resolve_save_link_mode({"link_profile": True}, profile_managed=False) == (
        "none",
        None,
    )
    assert resolve_save_link_mode(
        {"link_mode": "existing", "profile_id": "p1"},
        profile_managed=True,
    ) == ("existing", "p1")
    assert resolve_save_link_mode(
        {"link_mode": "existing"},
        profile_managed=True,
    ) == ("none", None)
    assert resolve_save_link_mode(
        {"link_mode": "create"},
        profile_managed=False,
    ) == ("none", None)
    assert resolve_save_link_mode({"link_mode": "none"}, profile_managed=True) == (
        "none",
        None,
    )
