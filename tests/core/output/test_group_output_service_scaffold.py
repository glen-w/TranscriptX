"""Unit tests for GroupOutputService disk scaffold and save helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.output.group_output_service import GroupOutputService


@pytest.mark.unit
def test_group_output_service_output_dir_joins_uuid_and_run_id(tmp_path: Path) -> None:
    service = GroupOutputService(
        group_uuid="group-abc",
        run_id="run-xyz",
        output_dir=str(tmp_path),
        scaffold_by_session=False,
        scaffold_by_speaker=False,
        scaffold_comparisons=False,
    )
    assert service.base_dir == tmp_path / "group-abc" / "run-xyz"
    assert (service.base_dir / "combined").is_dir()
    assert not (service.base_dir / "by_session").exists()
    assert not (service.base_dir / "by_speaker").exists()
    assert not (service.base_dir / "comparisons").exists()


@pytest.mark.unit
def test_group_output_service_scaffold_toggles(tmp_path: Path) -> None:
    service = GroupOutputService(
        group_uuid="g1",
        run_id="r1",
        output_dir=str(tmp_path),
        scaffold_by_session=True,
        scaffold_by_speaker=False,
        scaffold_comparisons=True,
    )
    assert (service.base_dir / "by_session").is_dir()
    assert not (service.base_dir / "by_speaker").exists()
    assert (service.base_dir / "comparisons").is_dir()


@pytest.mark.unit
def test_group_output_service_save_helpers_round_trip(tmp_path: Path) -> None:
    service = GroupOutputService(
        group_uuid="g2",
        run_id="r2",
        output_dir=str(tmp_path),
        scaffold_by_session=False,
        scaffold_by_speaker=False,
        scaffold_comparisons=False,
    )
    summary_path = Path(service.save_summary("hello group"))
    assert summary_path.read_text(encoding="utf-8") == "hello group"

    table_path = Path(service.save_session_table([{"a": 1, "b": "x"}]))
    assert table_path.exists()
    assert "a" in table_path.read_text(encoding="utf-8")

    json_path = Path(service.save_combined_json({"k": "v"}, "payload"))
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"k": "v"}

    csv_path = Path(service.save_combined_csv([{"n": 2}], "rows"))
    assert csv_path.exists()
    assert "n" in csv_path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_group_output_service_write_group_manifest(tmp_path: Path) -> None:
    service = GroupOutputService(
        group_uuid="g3",
        run_id="r3",
        output_dir=str(tmp_path),
        scaffold_by_session=False,
        scaffold_by_speaker=False,
        scaffold_comparisons=False,
    )
    path = Path(
        service.write_group_manifest(
            group_id="g3",
            group_key="grp_v1_abc",
            transcript_file_uuids=["u1", "u2"],
            transcript_paths=["/a.json", "/b.json"],
            run_id="r3",
        )
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["group_id"] == "g3"
    assert payload["group_key"] == "grp_v1_abc"
    assert payload["transcript_file_uuids"] == ["u1", "u2"]
    assert payload["transcript_ids"] == ["/a.json", "/b.json"]
    assert payload["run_id"] == "r3"
    assert "generated_at" in payload


@pytest.mark.unit
def test_group_run_metadata_empty_display_names_and_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.output.group_output_service.metadata.version",
        lambda _name: "9.9.9-test",
    )
    service = GroupOutputService(
        group_uuid="g4",
        run_id="r4",
        output_dir=str(tmp_path),
        scaffold_by_session=False,
        scaffold_by_speaker=False,
        scaffold_comparisons=False,
    )
    path = Path(
        service.write_group_run_metadata(
            group_uuid="g4",
            group_name_at_run="Named",
            group_key="grp_v1_x",
            member_transcript_ids=[1, 2],
            member_display_names=None,
            selected_modules=["stats"],
        )
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["member_display_names"] == []
    assert payload["member_count"] == 2
    assert payload["tx_version"] == "9.9.9-test"
    assert payload["run_id"] == "r4"
