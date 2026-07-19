"""Tests for group/member content helpers."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.web.blocks.group_content import (
    is_group_run,
    list_group_members,
    load_group_blob,
    load_group_content_rows,
    load_group_row_bundle,
    load_member_module_json,
)
from transcriptx.web.blocks.loader import ArtifactContentLoader
from transcriptx.web.models.artifact import Artifact


def test_is_group_run_and_list_members(tmp_path: Path) -> None:
    run = tmp_path / "group"
    run.mkdir()
    assert not is_group_run(run)
    (run / "group_member_runs.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "members": [
                    {
                        "order_index": 1,
                        "transcript_path": "/tmp/b.json",
                        "transcript_key": "k2",
                        "run_id": "r2",
                        "output_dir": str(tmp_path / "m2"),
                    },
                    {
                        "order_index": 0,
                        "transcript_path": "/tmp/a.json",
                        "transcript_key": "k1",
                        "run_id": "r1",
                        "output_dir": str(tmp_path / "m1"),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    assert is_group_run(run)
    members = list_group_members(run)
    assert [m.order_index for m in members] == [0, 1]
    assert members[0].label.startswith("1. a")


def test_load_group_content_rows_and_blob(tmp_path: Path) -> None:
    run = tmp_path / "group"
    (run / "highlights").mkdir(parents=True)
    rows = [{"text": "hello", "order_index": 0}]
    (run / "highlights" / "highlight_rows.json").write_text(
        json.dumps(rows), encoding="utf-8"
    )
    assert load_group_content_rows(run, "highlights", "highlight_rows") == rows

    (run / "summary").mkdir()
    blob = {"schema_version": 1, "summaries": [{"summary": "s0", "order_index": 0}]}
    (run / "summary" / "summary.json").write_text(json.dumps(blob), encoding="utf-8")
    assert load_group_blob(run, "summary", "summary") == blob


def test_load_member_module_json_prefers_data_global(tmp_path: Path) -> None:
    group = tmp_path / "group"
    member = tmp_path / "member"
    group.mkdir()
    wrong = member / "insights" / "other"
    right = member / "insights" / "data" / "global"
    wrong.mkdir(parents=True)
    right.mkdir(parents=True)
    (wrong / "x_insights.json").write_text(
        json.dumps({"key_themes": [{"phrase": "wrong"}]}), encoding="utf-8"
    )
    (right / "x_insights.json").write_text(
        json.dumps({"key_themes": [{"phrase": "right"}]}), encoding="utf-8"
    )
    (group / "group_member_runs.json").write_text(
        json.dumps(
            {
                "members": [
                    {
                        "order_index": 0,
                        "transcript_path": "/tmp/x.json",
                        "transcript_key": "k",
                        "run_id": "r",
                        "output_dir": str(member),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    members = list_group_members(group)
    loaded = load_member_module_json(None, members[0], "insights", "_insights.json")
    assert loaded == {"key_themes": [{"phrase": "right"}]}


def test_load_group_row_bundle(tmp_path: Path) -> None:
    run = tmp_path / "group"
    (run / "insights").mkdir(parents=True)
    (run / "insights" / "session_rows.json").write_text(
        json.dumps([{"order_index": 0, "theme_count": 2}]), encoding="utf-8"
    )
    (run / "insights" / "insight_rows.json").write_text(
        json.dumps([{"kind": "key_theme", "text": "x"}]), encoding="utf-8"
    )
    bundle = load_group_row_bundle(run, "insights", "insight_rows")
    assert len(bundle["session_rows"]) == 1
    assert len(bundle["content_rows"]) == 1


def test_loader_prefers_group_root_when_requested(tmp_path: Path) -> None:
    group = tmp_path / "group"
    member = tmp_path / "member"
    group.mkdir()
    member.mkdir()
    (group / "insights").mkdir()
    (group / "insights" / "insight_rows.json").write_text(
        json.dumps([{"text": "group"}]), encoding="utf-8"
    )
    (member / "insights").mkdir()
    (member / "insights" / "m_insights.json").write_text(
        json.dumps({"key_themes": []}), encoding="utf-8"
    )
    artifacts = (
        Artifact(
            id="g",
            kind="data_json",
            module="insights",
            scope=None,
            speaker=None,
            subview=None,
            slice_id=None,
            rel_path="insights/insight_rows.json",
            bytes=1,
            mtime="2026-01-01T00:00:00",
            mime="application/json",
            tags=[],
        ),
        Artifact(
            id="m",
            kind="data_json",
            module="insights",
            scope=None,
            speaker=None,
            subview=None,
            slice_id="member_0",
            rel_path="insights/m_insights.json",
            bytes=1,
            mtime="2026-01-01T00:00:00",
            mime="application/json",
            tags=["member_session"],
            storage_root=str(member.resolve()),
        ),
    )
    loader = ArtifactContentLoader(group, artifacts)
    group_payload = loader.load_json(
        "insights", "insight_rows.json", prefer_group_root=True
    )
    assert group_payload == [{"text": "group"}]


def test_loader_defaults_to_group_root_before_member(tmp_path: Path) -> None:
    group = tmp_path / "group"
    member = tmp_path / "member"
    group.mkdir()
    member.mkdir()
    (group / "highlights").mkdir()
    (group / "highlights" / "x_highlights.json").write_text(
        json.dumps({"themes": [{"label": "group"}]}), encoding="utf-8"
    )
    (member / "highlights").mkdir()
    (member / "highlights" / "y_highlights.json").write_text(
        json.dumps({"themes": [{"label": "member"}]}), encoding="utf-8"
    )
    artifacts = (
        Artifact(
            id="m",
            kind="data_json",
            module="highlights",
            scope=None,
            speaker=None,
            subview=None,
            slice_id="member_0",
            rel_path="highlights/y_highlights.json",
            bytes=1,
            mtime="2026-01-01T00:00:00",
            mime="application/json",
            tags=["member_session"],
            storage_root=str(member.resolve()),
        ),
        Artifact(
            id="g",
            kind="data_json",
            module="highlights",
            scope=None,
            speaker=None,
            subview=None,
            slice_id=None,
            rel_path="highlights/x_highlights.json",
            bytes=1,
            mtime="2026-01-01T00:00:00",
            mime="application/json",
            tags=[],
        ),
    )
    loader = ArtifactContentLoader(group, artifacts)
    payload = loader.load_json("highlights", "_highlights.json")
    assert payload == {"themes": [{"label": "group"}]}
