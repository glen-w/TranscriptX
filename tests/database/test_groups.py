from unittest.mock import MagicMock, patch

from transcriptx.core.domain.group import Group as DomainGroup
from transcriptx.core.services.group_service import GroupService
from transcriptx.database.models.group import Group as GroupModel, GroupMember
from transcriptx.database.models.transcript import TranscriptFile
from transcriptx.database.repositories.group import GroupRepository


def test_group_repository_persists_group_and_members(db_session):
    transcript_one = TranscriptFile(
        file_path="/tmp/one.json",
        file_name="one.json",
    )
    transcript_two = TranscriptFile(
        file_path="/tmp/two.json",
        file_name="two.json",
    )
    db_session.add_all([transcript_one, transcript_two])
    db_session.commit()

    repo = GroupRepository(db_session)
    group = repo.create_group(
        name="Workshop",
        group_type="merged_event",
        transcript_file_ids_ordered=[transcript_one.id, transcript_two.id],
    )

    stored = db_session.query(GroupModel).filter_by(uuid=group.uuid).first()
    assert stored is not None
    members = db_session.query(GroupMember).filter_by(group_id=stored.id).all()
    assert len(members) == 2
    expected_key = DomainGroup.compute_key([transcript_one.uuid, transcript_two.uuid])
    assert stored.key == expected_key


def test_group_resolve_by_uuid_key_and_name(db_session):
    transcript = TranscriptFile(
        file_path="/tmp/resolve.json",
        file_name="resolve.json",
    )
    db_session.add(transcript)
    db_session.commit()

    repo = GroupRepository(db_session)
    group = repo.create_group(
        name="ResolveTest",
        group_type="merged_event",
        transcript_file_ids_ordered=[transcript.id],
    )

    with patch(
        "transcriptx.core.services.group_service._get_session", return_value=db_session
    ):
        assert GroupService.resolve_group_identifier(group.uuid).uuid == group.uuid
        assert GroupService.resolve_group_identifier(group.key).uuid == group.uuid
        assert GroupService.resolve_group_identifier("ResolveTest").uuid == group.uuid


def test_group_resolve_ambiguous_name():
    group_one = DomainGroup(
        id=1,
        uuid="11111111-1111-1111-1111-111111111111",
        key="grp_v1_" + "a" * 64,
        transcript_file_uuids=["aaa"],
    )
    group_two = DomainGroup(
        id=2,
        uuid="22222222-2222-2222-2222-222222222222",
        key="grp_v1_" + "b" * 64,
        transcript_file_uuids=["bbb"],
    )
    with (
        patch("transcriptx.core.services.group_service._get_session") as mock_session,
        patch("transcriptx.core.services.group_service.GroupRepository") as mock_repo,
    ):
        mock_repo.return_value.get_by_uuid.return_value = None
        mock_repo.return_value.get_by_key.return_value = None
        mock_repo.return_value.list_by_name.return_value = [group_one, group_two]
        mock_session.return_value = MagicMock()
        try:
            GroupService.resolve_group_identifier("DuplicateName")
        except ValueError as exc:
            assert "Multiple groups share this name" in str(exc)
        else:
            raise AssertionError("Expected ValueError for ambiguous group name")


def test_group_repository_rename_group(db_session):
    transcript = TranscriptFile(
        file_path="/tmp/rename.json",
        file_name="rename.json",
    )
    db_session.add(transcript)
    db_session.commit()

    repo = GroupRepository(db_session)
    group = repo.create_group(
        name="Original",
        group_type="merged_event",
        transcript_file_ids_ordered=[transcript.id],
    )
    assert group.name == "Original"

    updated = repo.rename_group(group.id, "Renamed")
    assert updated is not None
    assert updated.name == "Renamed"
    assert updated.uuid == group.uuid

    db_session.expire_all()
    stored = db_session.query(GroupModel).filter_by(id=group.id).first()
    assert stored.name == "Renamed"


def test_group_repository_rename_group_returns_none_for_missing(db_session):
    repo = GroupRepository(db_session)
    result = repo.rename_group(99999, "Any")
    assert result is None


def test_group_repository_update_membership(db_session):
    one = TranscriptFile(file_path="/tmp/a.json", file_name="a.json")
    two = TranscriptFile(file_path="/tmp/b.json", file_name="b.json")
    three = TranscriptFile(file_path="/tmp/c.json", file_name="c.json")
    db_session.add_all([one, two, three])
    db_session.commit()

    repo = GroupRepository(db_session)
    group = repo.create_group(
        name="Reorder",
        group_type="merged_event",
        transcript_file_ids_ordered=[one.id, two.id],
    )
    members_before = repo.resolve_members(group.id)
    assert len(members_before) == 2
    assert [m.id for m in members_before] == [one.id, two.id]

    updated = repo.update_membership(group.id, [two.id, one.id, three.id])
    assert updated is not None
    assert updated.uuid == group.uuid
    members_after = repo.resolve_members(group.id)
    assert len(members_after) == 3
    assert [m.id for m in members_after] == [two.id, one.id, three.id]


def test_group_repository_update_membership_returns_none_for_missing(db_session):
    repo = GroupRepository(db_session)
    result = repo.update_membership(99999, [])
    assert result is None
