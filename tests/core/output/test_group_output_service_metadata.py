import json

from transcriptx.core.output.group_output_service import GroupOutputService


def test_group_run_metadata_written(tmp_path) -> None:
    service = GroupOutputService(
        group_uuid="group-123",
        run_id="run-456",
        output_dir=str(tmp_path),
    )
    service.write_group_run_metadata(
        group_uuid="group-123",
        group_name_at_run="Test Group",
        group_key="grp_v1_" + "a" * 64,
        member_transcript_ids=[1, 2, 3],
        member_display_names=["one.json", "two.json", "three.json"],
        selected_modules=["stats", "sentiment"],
    )

    path = service.base_dir / "group_run_metadata.json"
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["group_uuid"] == "group-123"
    assert payload["group_name_at_run"] == "Test Group"
    assert payload["group_key"].startswith("grp_v1_")
    assert payload["member_transcript_ids"] == [1, 2, 3]
    assert payload["member_count"] == 3
    assert payload["selected_modules"] == ["stats", "sentiment"]
