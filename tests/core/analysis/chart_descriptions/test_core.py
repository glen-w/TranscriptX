"""Unit tests for chart_descriptions core contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.analysis.chart_descriptions.chart_key import (
    build_chart_key_payload,
    build_logical_chart_id,
    chart_key_digest,
)
from transcriptx.core.analysis.chart_descriptions.generate import run_chart_descriptions
from transcriptx.core.analysis.chart_descriptions.inventory import (
    ChartRepresentation,
    LogicalChartInventory,
    make_descriptor_from_fields,
)
from transcriptx.core.analysis.chart_descriptions.path_safety import is_path_within_roots
from transcriptx.core.analysis.chart_descriptions.publisher import (
    active_matches_attempt,
    read_active,
    write_attempt_epoch,
)
from transcriptx.core.analysis.chart_descriptions.resolve import (
    resolve_chart_llm_description_by_key,
)
from transcriptx.core.analysis.chart_descriptions.selection import select_charts_for_set
from transcriptx.core.viz.specs import BarCategoricalSpec
from transcriptx.core.analysis.chart_descriptions.evidence import evidence_from_chart_spec


def test_chart_key_independent_of_format_presence():
    logical = build_logical_chart_id(
        module="stats",
        viz_id="stats.foo",
        scope="global",
        speaker_identity=None,
        name="foo",
    )
    payload = build_chart_key_payload(
        run_target_id="runA",
        logical_chart_id=logical,
        viz_id="stats.foo",
        scope="global",
        speaker_identity=None,
        slice_identity=None,
        source_run_id=None,
        member_session_id=None,
    )
    key = chart_key_digest(payload)
    # Same key whether we later attach png, html, or both
    assert len(key) == 64
    assert key == chart_key_digest(payload)


def test_static_only_and_dynamic_only_share_logical_id():
    logical = build_logical_chart_id(
        module="m", viz_id="v", scope="global", speaker_identity=None, name="n"
    )
    d1 = make_descriptor_from_fields(
        viz_id="v",
        module="m",
        scope="global",
        speaker=None,
        slice_id=None,
        title="t",
        run_kind="transcript",
        provenance_kind="transcript",
        run_target_id="r",
        source_run_id=None,
        member_session_id=None,
        name="n",
        representations=[
            ChartRepresentation(
                artifact_id="a1", rel_path="m/charts/x.png", kind="chart_static", format="png"
            )
        ],
    )
    d2 = make_descriptor_from_fields(
        viz_id="v",
        module="m",
        scope="global",
        speaker=None,
        slice_id=None,
        title="t",
        run_kind="transcript",
        provenance_kind="transcript",
        run_target_id="r",
        source_run_id=None,
        member_session_id=None,
        name="n",
        representations=[
            ChartRepresentation(
                artifact_id="a2", rel_path="m/charts/x.html", kind="chart_dynamic", format="html"
            )
        ],
    )
    assert d1.chart_key == d2.chart_key
    assert d1.logical_chart_id == logical


def test_transcript_group_excludes_member_embeds():
    charts = [
        make_descriptor_from_fields(
            viz_id="g.a",
            module="stats",
            scope="global",
            speaker=None,
            slice_id=None,
            title=None,
            run_kind="group",
            provenance_kind="group_aggregate",
            run_target_id="g",
            source_run_id=None,
            member_session_id=None,
        ),
        make_descriptor_from_fields(
            viz_id="t.a",
            module="stats",
            scope="global",
            speaker=None,
            slice_id=None,
            title=None,
            run_kind="group",
            provenance_kind="member_session",
            run_target_id="g",
            source_run_id="m1",
            member_session_id="m1",
        ),
    ]
    selected = select_charts_for_set(charts, chart_set="transcript_group", run_kind="group")
    assert len(selected) == 1
    assert selected[0].provenance_kind == "group_aggregate"


def test_path_safety_realpath(tmp_path: Path):
    root = tmp_path / "run"
    root.mkdir()
    inside = root / "ok.txt"
    inside.write_text("x", encoding="utf-8")
    assert is_path_within_roots(inside, [root])
    outside = tmp_path / "other.txt"
    outside.write_text("y", encoding="utf-8")
    assert not is_path_within_roots(outside, [root])


def test_evidence_from_bar_spec():
    spec = BarCategoricalSpec(
        viz_id="acts.pie",
        module="acts",
        name="pie",
        scope="global",
        chart_intent="bar_categorical",
        title="Acts",
        categories=["a", "b"],
        values=[1.0, 2.0],
    )
    ev = evidence_from_chart_spec(spec)
    assert ev.labels == ["a", "b"]
    assert ev.values == [1.0, 2.0]
    assert ev.content_sha256()


class _FakeClient:
    def __init__(self) -> None:
        self.calls = 0
        self.model = "fake"

    def generate(self, prompt, system_prompt=None, temperature=0.0, response_format=None):
        self.calls += 1
        return json.dumps({"description": "The chart shows categories a and b."})


def test_skipped_gate_zero_client_calls(tmp_path: Path):
    run_root = tmp_path / "run"
    run_root.mkdir()
    inventory = LogicalChartInventory(
        run_root=str(run_root),
        run_kind="transcript",
        run_target_id="t1",
        charts=[],
    )
    client = _FakeClient()
    result = run_chart_descriptions(
        run_root=run_root,
        run_id="r1",
        inventory=inventory,
        inventory_snapshot_sha256=inventory.snapshot_sha256(),
        chart_set="all",
        selected=True,
        enabled=True,
        llm_enabled=False,
        config=type("C", (), {"analysis": None, "llm": None})(),
        client_factory=lambda: client,
    )
    assert result.attempt_status == "skipped"
    assert result.published
    assert client.calls == 0
    assert active_matches_attempt(run_root)


def test_generation_and_resolve(tmp_path: Path):
    run_root = tmp_path / "run"
    run_root.mkdir()
    chart = make_descriptor_from_fields(
        viz_id="acts.pie",
        module="acts",
        scope="global",
        speaker=None,
        slice_id=None,
        title="Acts mix",
        run_kind="transcript",
        provenance_kind="transcript",
        run_target_id="t1",
        source_run_id=None,
        member_session_id=None,
        name="pie",
        registry_description="Dialogue act mix",
        representations=[
            ChartRepresentation(
                artifact_id="x",
                rel_path="acts/charts/global/static/pie.png",
                kind="chart_static",
                format="png",
            )
        ],
    )
    # Write evidence sidecar
    ev_path = run_root / "acts/charts/global/static/pie.evidence.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    from transcriptx.core.analysis.chart_descriptions.evidence import ChartEvidence

    evidence = ChartEvidence(
        viz_id="acts.pie",
        module="acts",
        scope="global",
        title="Acts mix",
        labels=["q", "a"],
        values=[3, 7],
    )
    ev_path.write_text(json.dumps(evidence.to_dict()), encoding="utf-8")
    chart = make_descriptor_from_fields(
        viz_id=chart.viz_id,
        module=chart.module,
        scope=chart.scope,
        speaker=None,
        slice_id=None,
        title=chart.title,
        run_kind="transcript",
        provenance_kind="transcript",
        run_target_id="t1",
        source_run_id=None,
        member_session_id=None,
        name="pie",
        evidence_rel_path="acts/charts/global/static/pie.evidence.json",
        evidence_sha256=evidence.content_sha256(),
        representations=list(chart.representations),
        registry_description=chart.registry_description,
    )
    inventory = LogicalChartInventory(
        run_root=str(run_root),
        run_kind="transcript",
        run_target_id="t1",
        charts=[chart],
    )
    client = _FakeClient()
    result = run_chart_descriptions(
        run_root=run_root,
        run_id="r1",
        inventory=inventory,
        inventory_snapshot_sha256=inventory.snapshot_sha256(),
        chart_set="all",
        selected=True,
        enabled=True,
        llm_enabled=True,
        config=type(
            "C",
            (),
            {
                "analysis": type(
                    "A",
                    (),
                    {
                        "chart_descriptions": type(
                            "CD",
                            (),
                            {
                                "max_description_chars": 1200,
                                "max_retries": 0,
                                "circuit_breaker_failures": 3,
                            },
                        )()
                    },
                )(),
                "llm": type("L", (), {"model": "fake"})(),
            },
        )(),
        client_factory=lambda: client,
    )
    assert result.published
    assert client.calls == 1
    text = resolve_chart_llm_description_by_key(run_root, chart.chart_key)
    assert text is not None
    assert "chart" in text.lower() or "categories" in text.lower()


def test_stale_active_without_matching_epoch(tmp_path: Path):
    run_root = tmp_path / "run"
    run_root.mkdir()
    # Write ACTIVE without matching attempt
    from transcriptx.core.analysis.chart_descriptions.publisher import write_active

    write_active(
        run_root,
        generation_id="gen1",
        attempt_epoch="epoch-old",
        overall_status="success",
        inventory_snapshot_sha256="abc",
        chart_set="all",
    )
    write_attempt_epoch(run_root, attempt_epoch="epoch-new", generation_id="gen2")
    assert not active_matches_attempt(run_root)
    assert resolve_chart_llm_description_by_key(run_root, "anything") is None


def test_default_all_does_not_mass_skip_without_evidence_sidecar(tmp_path: Path):
    """Legacy metadata fallback still selects charts under chart_set=all."""
    charts = [
        make_descriptor_from_fields(
            viz_id=f"viz.{i}",
            module="stats",
            scope="global",
            speaker=None,
            slice_id=None,
            title=f"Chart {i}",
            run_kind="transcript",
            provenance_kind="transcript",
            run_target_id="t",
            source_run_id=None,
            member_session_id=None,
            name=f"n{i}",
            registry_description="help",
        )
        for i in range(5)
    ]
    selected = select_charts_for_set(charts, chart_set="all", run_kind="transcript")
    assert len(selected) == 5
