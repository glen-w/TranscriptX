"""Additional selector / overview / reuse coverage for chart_descriptions."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.analysis.chart_descriptions.generate import run_chart_descriptions
from transcriptx.core.analysis.chart_descriptions.inventory import (
    ChartRepresentation,
    LogicalChartInventory,
    make_descriptor_from_fields,
)
from transcriptx.core.analysis.chart_descriptions.overview import resolve_overview_viz_ids
from transcriptx.core.analysis.chart_descriptions.paths import generation_dir
from transcriptx.core.analysis.chart_descriptions.selection import select_charts_for_set


def test_overview_only_uses_core_utility_not_session_filters():
    # Core utility returns registry defaults independent of any Streamlit state
    ids = resolve_overview_viz_ids(run_kind="transcript", user_overview=None, max_items=3)
    assert isinstance(ids, list)
    assert len(ids) <= 3
    charts = [
        make_descriptor_from_fields(
            viz_id=vid or "missing",
            module="m",
            scope="global",
            speaker=None,
            slice_id=None,
            title=None,
            run_kind="transcript",
            provenance_kind="transcript",
            run_target_id="t",
            source_run_id=None,
            member_session_id=None,
            name=vid,
        )
        for vid in (ids + ["not.in.overview"])
    ]
    # Force one known overview id if list empty
    if not ids:
        return
    selected = select_charts_for_set(
        charts, chart_set="overview_only", run_kind="transcript"
    )
    assert all(c.viz_id in ids for c in selected)
    assert "not.in.overview" not in {c.viz_id for c in selected}


def test_reuse_copies_into_new_generation(tmp_path: Path):
    run_root = tmp_path / "run"
    run_root.mkdir()
    ev_path = run_root / "m/charts/x.evidence.json"
    ev_path.parent.mkdir(parents=True)
    from transcriptx.core.analysis.chart_descriptions.evidence import ChartEvidence

    evidence = ChartEvidence(
        viz_id="v1", module="m", scope="global", title="T", labels=["a"], values=[1]
    )
    ev_path.write_text(json.dumps(evidence.to_dict()), encoding="utf-8")
    chart = make_descriptor_from_fields(
        viz_id="v1",
        module="m",
        scope="global",
        speaker=None,
        slice_id=None,
        title="T",
        run_kind="transcript",
        provenance_kind="transcript",
        run_target_id="t",
        source_run_id=None,
        member_session_id=None,
        name="x",
        evidence_rel_path="m/charts/x.evidence.json",
        evidence_sha256=evidence.content_sha256(),
        representations=[
            ChartRepresentation(
                artifact_id="a",
                rel_path="m/charts/x.png",
                kind="chart_static",
                format="png",
            )
        ],
        registry_description="help",
    )
    inventory = LogicalChartInventory(
        run_root=str(run_root),
        run_kind="transcript",
        run_target_id="t",
        charts=[chart],
    )
    snap = inventory.snapshot_sha256()

    class Client:
        def __init__(self):
            self.calls = 0
            self.model = "fake"

        def generate(self, *a, **k):
            self.calls += 1
            return json.dumps({"description": "Narrative one."})

    client = Client()
    cfg = type(
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
    )()
    r1 = run_chart_descriptions(
        run_root=run_root,
        run_id="r",
        inventory=inventory,
        inventory_snapshot_sha256=snap,
        chart_set="all",
        selected=True,
        enabled=True,
        llm_enabled=True,
        config=cfg,
        client_factory=lambda: client,
    )
    assert r1.published and client.calls == 1
    gen1 = r1.generation_id
    r2 = run_chart_descriptions(
        run_root=run_root,
        run_id="r",
        inventory=inventory,
        inventory_snapshot_sha256=snap,
        chart_set="all",
        selected=True,
        enabled=True,
        llm_enabled=True,
        config=cfg,
        client_factory=lambda: client,
    )
    assert r2.published
    assert client.calls == 1  # reused, no new LLM call
    assert r2.generation_id != gen1
    # New generation must contain its own copy, not a path into gen1
    desc_files = list((generation_dir(run_root, r2.generation_id) / "descriptions").glob("*.json"))
    assert desc_files
    payload = json.loads(desc_files[0].read_text(encoding="utf-8"))
    assert payload.get("reused") is True
    assert payload.get("description") == "Narrative one."
