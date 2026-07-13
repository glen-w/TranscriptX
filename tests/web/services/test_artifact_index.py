"""Tests for dual-dimension artifact presentation index."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services.artifact_index import (
    ArtifactSourceFilter,
    build_artifact_index_uncached,
    build_entry,
    classify_artifact_role,
    classify_source_kind,
    file_signature,
    filter_by_source,
    order_artifacts_for_browse,
    order_entries_for_charts,
    order_modules_for_charts,
    _format_size,
    _preview_eligible,
)


def _artifact(**kwargs) -> Artifact:
    base = dict(
        id="a1",
        kind="data_json",
        module="stats",
        scope="global",
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path="stats/data/global/x_stats.json",
        bytes=12,
        mtime="2024-01-01T00:00:00Z",
        mime="application/json",
        tags=[],
        title="stats",
    )
    base.update(kwargs)
    return Artifact.from_dict(base)


def test_classify_summary_role() -> None:
    a = _artifact(
        module="llm_summary",
        rel_path="llm_summary/data/global/x_llm_summary.json",
        title="LLM Summary",
    )
    assert classify_artifact_role(a) == "summary"


def test_classify_chart_role() -> None:
    a = _artifact(
        kind="chart_static",
        module="sentiment",
        rel_path="sentiment/charts/global/x.png",
        mime="image/png",
    )
    assert classify_artifact_role(a) == "chart"


def test_browse_orders_summary_before_structured() -> None:
    summary = build_entry(
        _artifact(
            id="s",
            module="llm_summary",
            rel_path="llm_summary/data/global/x_llm_summary.json",
        ),
        is_group_run=False,
    )
    structured = build_entry(
        _artifact(id="d", module="stats", rel_path="stats/data/global/x.json"),
        is_group_run=False,
    )
    ordered = order_artifacts_for_browse([structured, summary])
    assert ordered[0].id == "s"
    assert ordered[1].id == "d"


def test_charts_module_order_uses_taxonomy() -> None:
    entries = [
        build_entry(
            _artifact(id="1", module="sentiment", kind="chart_static"),
            is_group_run=False,
        ),
        build_entry(
            _artifact(id="2", module="llm_summary", kind="chart_static"),
            is_group_run=False,
        ),
        build_entry(
            _artifact(id="3", module="stats", kind="chart_static"),
            is_group_run=False,
        ),
    ]
    assert order_modules_for_charts(entries) == ["llm_summary", "stats", "sentiment"]


def test_member_session_source_and_filter() -> None:
    member = build_entry(
        _artifact(
            id="m",
            tags=["member_session"],
            storage_root="/tmp/member_run",
            title="MemberA: chart",
            kind="chart_static",
        ),
        is_group_run=True,
    )
    aggregate = build_entry(
        _artifact(id="g", kind="chart_static", module="stats"),
        is_group_run=True,
    )
    assert member.source_kind == "member_session"
    assert aggregate.source_kind == "group_aggregate"
    assert classify_source_kind(member.artifact) == "member_session"
    only_members = filter_by_source(
        [member, aggregate], ArtifactSourceFilter.MEMBER_SESSIONS
    )
    assert [e.id for e in only_members] == ["m"]
    only_agg = filter_by_source(
        [member, aggregate], ArtifactSourceFilter.GROUP_AGGREGATE
    )
    assert [e.id for e in only_agg] == ["g"]


def test_build_index_from_manifest(tmp_path: Path) -> None:
    run = tmp_path / "run1"
    run.mkdir()
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_type": "artifact_manifest",
                "schema_version": 1,
                "run_id": "run1",
                "artifacts": [
                    {
                        "id": "llm1",
                        "kind": "data_json",
                        "module": "llm_summary",
                        "scope": "global",
                        "rel_path": "llm_summary/data/global/x_llm_summary.json",
                        "bytes": 10,
                        "mtime": "2024-01-01T00:00:00Z",
                        "mime": "application/json",
                        "tags": [],
                        "title": "LLM",
                    },
                    {
                        "id": "st1",
                        "kind": "data_json",
                        "module": "stats",
                        "scope": "global",
                        "rel_path": "stats/data/global/x.json",
                        "bytes": 10,
                        "mtime": "2024-01-01T00:00:00Z",
                        "mime": "application/json",
                        "tags": [],
                        "title": "Stats",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    index = build_artifact_index_uncached(
        run, subject_scope="transcript", subject_id="s", run_id="run1"
    )
    assert len(index.entries) == 2
    browsed = order_artifacts_for_browse(index.entries)
    assert browsed[0].artifact.module == "llm_summary"


def test_classify_diagnostics_report_and_raw_roles() -> None:
    assert (
        classify_artifact_role(
            _artifact(
                id="m",
                rel_path="manifest.json",
                kind="other",
                module="",
                title="manifest",
            )
        )
        == "diagnostics"
    )
    assert (
        classify_artifact_role(
            _artifact(id="r", rel_path="report.md", kind="other", module="")
        )
        == "report"
    )
    assert (
        classify_artifact_role(
            _artifact(
                id="raw",
                kind="binary",
                module="assets",
                rel_path="assets/blob.bin",
                mime="application/octet-stream",
            )
        )
        == "raw_technical"
    )
    assert (
        classify_artifact_role(
            _artifact(
                id="stem",
                module="custom",
                rel_path="custom/data/global/x_summary.json",
                title="x",
            )
        )
        == "summary"
    )


def test_format_size_and_preview_eligible() -> None:
    assert _format_size(12) == "12 B"
    assert _format_size(2048).endswith("KB")
    assert _format_size(2 * 1024 * 1024).endswith("MB")
    assert _format_size(2 * 1024 * 1024 * 1024).endswith("GB")
    assert _preview_eligible(_artifact(kind="chart_static", mime="image/png"))
    assert _preview_eligible(_artifact(kind="data_json", mime="application/json"))
    assert _preview_eligible(
        _artifact(kind="other", mime="text/plain", rel_path="notes.txt")
    )
    assert not _preview_eligible(
        _artifact(kind="other", mime="application/octet-stream", rel_path="x.bin")
    )


def test_order_entries_for_charts_and_count_by_role(tmp_path: Path) -> None:
    entries = [
        build_entry(
            _artifact(id="1", module="sentiment", kind="chart_static"),
            is_group_run=False,
        ),
        build_entry(
            _artifact(id="2", module="stats", kind="chart_static", title="A"),
            is_group_run=False,
        ),
        build_entry(
            _artifact(id="3", module="stats", kind="data_json"),
            is_group_run=False,
        ),
    ]
    charts = order_entries_for_charts([e for e in entries if e.is_chart])
    assert charts[0].module == "stats"
    missing = file_signature(tmp_path / "nope.json")
    assert missing == "missing"
    present = tmp_path / "present.json"
    present.write_text("{}", encoding="utf-8")
    assert ":" in file_signature(present)

    empty_run = tmp_path / "empty_run"
    empty_run.mkdir()
    index = build_artifact_index_uncached(
        empty_run, subject_scope="transcript", subject_id="s", run_id="r"
    )
    assert index.count_by_role() == {}
    assert index.by_id() == {}
    assert index.chart_entries() == []

    groupish = build_entry(
        _artifact(id="g", kind="data_json", module="stats"),
        is_group_run=True,
    )
    assert groupish.source_kind == "group_aggregate"
    assert filter_by_source([groupish], "all") == [groupish]
