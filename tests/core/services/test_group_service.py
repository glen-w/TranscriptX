"""Tests for core GroupService (rename, update_membership, create_or_get_group_with_status)."""

from unittest.mock import patch

import pytest

from transcriptx.core.domain.group import Group as DomainGroup
from transcriptx.core.services.group_service import GroupService
from transcriptx.database.models.transcript import TranscriptFile
from transcriptx.database.repositories.group import GroupRepository


def test_rename_group_success(db_session):
    transcript = TranscriptFile(
        file_path="/tmp/rename_svc.json",
        file_name="rename_svc.json",
    )
    db_session.add(transcript)
    db_session.commit()

    repo = GroupRepository(db_session)
    group = repo.create_group(
        name="Before",
        group_type="merged_event",
        transcript_file_ids_ordered=[transcript.id],
    )

    with patch(
        "transcriptx.core.services.group_service._get_session",
        return_value=db_session,
    ):
        updated = GroupService.rename_group(group.uuid, "After")
    assert updated.name == "After"
    assert updated.uuid == group.uuid


def test_rename_group_strips_whitespace(db_session):
    transcript = TranscriptFile(
        file_path="/tmp/ws.json",
        file_name="ws.json",
    )
    db_session.add(transcript)
    db_session.commit()

    repo = GroupRepository(db_session)
    group = repo.create_group(
        name="X",
        group_type="merged_event",
        transcript_file_ids_ordered=[transcript.id],
    )

    with patch(
        "transcriptx.core.services.group_service._get_session",
        return_value=db_session,
    ):
        updated = GroupService.rename_group(group.uuid, "  Y  ")
    assert updated.name == "Y"


def test_rename_group_noop_when_unchanged(db_session):
    transcript = TranscriptFile(
        file_path="/tmp/same.json",
        file_name="same.json",
    )
    db_session.add(transcript)
    db_session.commit()

    repo = GroupRepository(db_session)
    group = repo.create_group(
        name="Same",
        group_type="merged_event",
        transcript_file_ids_ordered=[transcript.id],
    )

    with patch(
        "transcriptx.core.services.group_service._get_session",
        return_value=db_session,
    ):
        result = GroupService.rename_group(group.uuid, "Same")
    assert result.name == "Same"
    assert result.uuid == group.uuid


def test_rename_group_rejects_empty_name(db_session):
    transcript = TranscriptFile(
        file_path="/tmp/e.json",
        file_name="e.json",
    )
    db_session.add(transcript)
    db_session.commit()

    repo = GroupRepository(db_session)
    group = repo.create_group(
        name="Ok",
        group_type="merged_event",
        transcript_file_ids_ordered=[transcript.id],
    )

    with patch(
        "transcriptx.core.services.group_service._get_session",
        return_value=db_session,
    ):
        with pytest.raises(ValueError, match="cannot be empty"):
            GroupService.rename_group(group.uuid, "   ")
        with pytest.raises(ValueError, match="cannot be empty"):
            GroupService.rename_group(group.uuid, "")


def test_rename_group_rejects_non_persisted():
    group_no_id = DomainGroup(
        id=None,
        uuid="00000000-0000-0000-0000-000000000001",
        key="grp_v1_" + "a" * 64,
        transcript_file_uuids=[],
    )
    with (
        patch(
            "transcriptx.core.services.group_service._get_session",
        ),
        patch(
            "transcriptx.core.services.group_service.GroupService.resolve_group_identifier",
            return_value=group_no_id,
        ),
    ):
        with pytest.raises(ValueError, match="non-persisted"):
            GroupService.rename_group(group_no_id.uuid, "X")


def test_update_membership_success(db_session):
    one = TranscriptFile(file_path="/tmp/u1.json", file_name="u1.json")
    two = TranscriptFile(file_path="/tmp/u2.json", file_name="u2.json")
    db_session.add_all([one, two])
    db_session.commit()

    repo = GroupRepository(db_session)
    group = repo.create_group(
        name="U",
        group_type="merged_event",
        transcript_file_ids_ordered=[one.id],
    )

    with patch(
        "transcriptx.core.services.group_service._get_session",
        return_value=db_session,
    ):
        updated = GroupService.update_membership(
            group.uuid,
            [two.uuid, one.uuid],
        )
    assert updated is not None
    assert updated.transcript_file_uuids == [two.uuid, one.uuid]


def test_update_membership_rejects_non_persisted():
    group_no_id = DomainGroup(
        id=None,
        uuid="00000000-0000-0000-0000-000000000002",
        key="grp_v1_" + "b" * 64,
        transcript_file_uuids=[],
    )
    with (
        patch(
            "transcriptx.core.services.group_service._get_session",
        ),
        patch(
            "transcriptx.core.services.group_service.GroupService.resolve_group_identifier",
            return_value=group_no_id,
        ),
    ):
        with pytest.raises(ValueError, match="non-persisted"):
            GroupService.update_membership(group_no_id.uuid, ["some-uuid"])


def test_update_membership_invalid_refs_raises(db_session):
    transcript = TranscriptFile(
        file_path="/tmp/valid.json",
        file_name="valid.json",
    )
    db_session.add(transcript)
    db_session.commit()

    repo = GroupRepository(db_session)
    group = repo.create_group(
        name="V",
        group_type="merged_event",
        transcript_file_ids_ordered=[transcript.id],
    )

    with patch(
        "transcriptx.core.services.group_service._get_session",
        return_value=db_session,
    ):
        with pytest.raises(ValueError, match="not found"):
            GroupService.update_membership(
                group.uuid,
                [transcript.uuid, "00000000-0000-0000-0000-000000000099"],
            )


def test_create_or_get_group_with_status_returns_created_true_when_new(db_session):
    transcript = TranscriptFile(
        file_path="/tmp/new.json",
        file_name="new.json",
    )
    db_session.add(transcript)
    db_session.commit()

    with patch(
        "transcriptx.core.services.group_service._get_session",
        return_value=db_session,
    ):
        group, created = GroupService.create_or_get_group_with_status(
            name="NewGroup",
            group_type="merged_event",
            transcript_refs=[transcript.uuid],
        )
    assert created is True
    assert group.name == "NewGroup"
    assert group.transcript_file_uuids == [transcript.uuid]


def test_create_or_get_group_with_status_returns_created_false_when_exists(db_session):
    transcript = TranscriptFile(
        file_path="/tmp/exist.json",
        file_name="exist.json",
    )
    db_session.add(transcript)
    db_session.commit()

    with patch(
        "transcriptx.core.services.group_service._get_session",
        return_value=db_session,
    ):
        group1, created1 = GroupService.create_or_get_group_with_status(
            name="First",
            group_type="merged_event",
            transcript_refs=[transcript.uuid],
        )
        group2, created2 = GroupService.create_or_get_group_with_status(
            name="Second",
            group_type="merged_event",
            transcript_refs=[transcript.uuid],
        )
    assert created1 is True
    assert created2 is False
    assert group1.uuid == group2.uuid
    assert group2.name == "First"


def test_create_or_get_group_still_returns_group_only(db_session):
    transcript = TranscriptFile(
        file_path="/tmp/legacy.json",
        file_name="legacy.json",
    )
    db_session.add(transcript)
    db_session.commit()

    with patch(
        "transcriptx.core.services.group_service._get_session",
        return_value=db_session,
    ):
        result = GroupService.create_or_get_group(
            name="Legacy",
            group_type="merged_event",
            transcript_refs=[transcript.uuid],
        )
    assert isinstance(result, DomainGroup)
    assert result.name == "Legacy"
    assert not isinstance(result, tuple)


def test_delete_group_success(db_session):
    transcript = TranscriptFile(
        file_path="/tmp/del.json",
        file_name="del.json",
    )
    db_session.add(transcript)
    db_session.commit()

    repo = GroupRepository(db_session)
    group = repo.create_group(
        name="ToDelete",
        group_type="merged_event",
        transcript_file_ids_ordered=[transcript.id],
    )

    with patch(
        "transcriptx.core.services.group_service._get_session",
        return_value=db_session,
    ):
        ok = GroupService.delete_group(group.uuid)
    assert ok is True
    db_session.expire_all()
    from transcriptx.database.models.group import Group as GroupModel

    stored = db_session.query(GroupModel).filter_by(uuid=group.uuid).first()
    assert stored is None


def test_list_groups_with_type_filter(db_session):
    transcript = TranscriptFile(
        file_path="/tmp/lt.json",
        file_name="lt.json",
    )
    db_session.add(transcript)
    db_session.commit()

    repo = GroupRepository(db_session)
    repo.create_group(
        name="Merged",
        group_type="merged_event",
        transcript_file_ids_ordered=[transcript.id],
    )

    with patch(
        "transcriptx.core.services.group_service._get_session",
        return_value=db_session,
    ):
        all_groups = GroupService.list_groups()
        merged = GroupService.list_groups(group_type="merged_event")
    assert len(all_groups) >= 1
    assert len(merged) >= 1
    assert all(g.type == "merged_event" for g in merged)


def test_get_members(db_session):
    one = TranscriptFile(file_path="/tmp/m1.json", file_name="m1.json")
    two = TranscriptFile(file_path="/tmp/m2.json", file_name="m2.json")
    db_session.add_all([one, two])
    db_session.commit()

    repo = GroupRepository(db_session)
    group = repo.create_group(
        name="Members",
        group_type="merged_event",
        transcript_file_ids_ordered=[one.id, two.id],
    )

    with patch(
        "transcriptx.core.services.group_service._get_session",
        return_value=db_session,
    ):
        members = GroupService.get_members(group.id)
    assert len(members) == 2
    ids = [m.id for m in members]
    assert one.id in ids and two.id in ids
