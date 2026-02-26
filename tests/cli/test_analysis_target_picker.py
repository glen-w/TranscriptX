from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.cli.analysis_target_picker import hydrate_group_selection
from transcriptx.core.pipeline.target_resolver import GroupRef, resolve_group_member_ids
from transcriptx.database.models.transcript import TranscriptFile
from transcriptx.database.repositories.group import GroupRepository


@pytest.mark.database
def test_hydrate_group_selection_preserves_order(db_session) -> None:
    first = TranscriptFile(file_path="/tmp/first.json", file_name="first.json")
    second = TranscriptFile(file_path="/tmp/second.json", file_name="second.json")
    third = TranscriptFile(file_path="/tmp/third.json", file_name="third.json")
    db_session.add_all([first, second, third])
    db_session.commit()

    repo = GroupRepository(db_session)
    group = repo.create_group(
        name="OrderCheck",
        group_type="merged_event",
        transcript_file_ids_ordered=[second.id, first.id, third.id],
    )

    with (
        patch(
            "transcriptx.core.services.group_service.get_session",
            return_value=db_session,
        ),
        patch(
            "transcriptx.core.pipeline.target_resolver.get_session",
            return_value=db_session,
        ),
    ):
        selection = hydrate_group_selection(GroupRef(group_uuid=group.uuid))
        assert selection.member_transcript_ids == [second.id, first.id, third.id]
        assert selection.member_paths == [
            Path(second.file_path),
            Path(first.file_path),
            Path(third.file_path),
        ]
        resolved_ids = resolve_group_member_ids(GroupRef(group_uuid=group.uuid))
        assert resolved_ids == [second.id, first.id, third.id]
