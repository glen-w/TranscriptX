"""Tests for web GroupService (delegation to core)."""

from unittest.mock import patch

from transcriptx.core.domain.group import Group
from transcriptx.web.services.group_service import GroupService


def test_rename_group_delegates_to_core():
    fake_group = Group(
        uuid="g-uuid",
        key="grp_v1_" + "a" * 64,
        transcript_file_uuids=[],
        name="Renamed",
    )
    with patch(
        "transcriptx.web.services.group_service.CoreGroupService.rename_group",
        return_value=fake_group,
    ) as mock_rename:
        result = GroupService.rename_group("g-uuid", "Renamed")
    mock_rename.assert_called_once_with("g-uuid", "Renamed")
    assert result is fake_group


def test_update_membership_delegates_to_core():
    fake_group = Group(
        uuid="g-uuid",
        key="grp_v1_" + "b" * 64,
        transcript_file_uuids=["u1", "u2"],
    )
    refs = ["u1", "u2"]
    with patch(
        "transcriptx.web.services.group_service.CoreGroupService.update_membership",
        return_value=fake_group,
    ) as mock_update:
        result = GroupService.update_membership("g-uuid", refs)
    mock_update.assert_called_once_with("g-uuid", refs)
    assert result is fake_group


def test_create_group_with_status_delegates_to_core():
    fake_group = Group(
        uuid="g-uuid",
        key="grp_v1_" + "c" * 64,
        transcript_file_uuids=["u1"],
        name="New",
    )
    with patch(
        "transcriptx.web.services.group_service.CoreGroupService.create_or_get_group_with_status",
        return_value=(fake_group, True),
    ) as mock_create:
        group, created = GroupService.create_group_with_status(
            name="New",
            group_type="merged_event",
            transcript_refs=["u1"],
        )
    mock_create.assert_called_once()
    call_kw = mock_create.call_args[1]
    assert call_kw["name"] == "New"
    assert call_kw["group_type"] == "merged_event"
    assert call_kw["transcript_refs"] == ["u1"]
    assert group is fake_group
    assert created is True


def test_list_groups_delegates_to_core():
    with patch(
        "transcriptx.web.services.group_service.CoreGroupService.list_groups",
        return_value=[],
    ) as mock_list:
        GroupService.list_groups(group_type="merged_event")
    mock_list.assert_called_once_with(group_type="merged_event")


def test_delete_group_delegates_to_core():
    with patch(
        "transcriptx.web.services.group_service.CoreGroupService.delete_group",
        return_value=True,
    ) as mock_del:
        result = GroupService.delete_group("g-uuid")
    mock_del.assert_called_once_with("g-uuid")
    assert result is True
