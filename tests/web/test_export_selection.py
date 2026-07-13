"""Export selection resolution tests."""

from __future__ import annotations

from transcriptx.web.components.export_panel import resolve_export_selection
from transcriptx.web.models.artifact import Artifact


def _a(**kwargs) -> Artifact:
    base = dict(
        id="1",
        kind="data_json",
        module="stats",
        scope="global",
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path="stats/x.json",
        bytes=1,
        mtime="",
        mime="application/json",
        tags=[],
    )
    base.update(kwargs)
    return Artifact.from_dict(base)


def test_export_modes_parity() -> None:
    arts = [
        _a(id="c1", kind="chart_static", module="sentiment", rel_path="c1.png"),
        _a(id="c2", kind="chart_dynamic", module="sentiment", rel_path="c2.html"),
        _a(id="d1", kind="data_json", module="stats", rel_path="d1.json"),
        _a(id="d2", kind="data_csv", module="stats", speaker="A", rel_path="d2.csv"),
    ]
    assert len(resolve_export_selection(arts, "All")) == 4
    assert {a.id for a in resolve_export_selection(arts, "Charts Only")} == {"c1", "c2"}
    assert {a.id for a in resolve_export_selection(arts, "Static Charts Only")} == {
        "c1"
    }
    assert {a.id for a in resolve_export_selection(arts, "Data Only")} == {"d1", "d2"}
    assert {
        a.id for a in resolve_export_selection(arts, "Module", module_choice="stats")
    } == {"d1", "d2"}
    assert {
        a.id for a in resolve_export_selection(arts, "Speaker", speaker_choice="A")
    } == {"d2"}
    assert {
        a.id
        for a in resolve_export_selection(
            arts, "Custom Selection", custom_ids=["c1", "d1"]
        )
    } == {"c1", "d1"}
    assert {
        a.id for a in resolve_export_selection(arts, "Selected", preselected_ids=["c2"])
    } == {"c2"}


def test_custom_selection_falls_back_to_preselected_ids() -> None:
    arts = [
        _a(id="c1", kind="chart_static", module="sentiment", rel_path="c1.png"),
        _a(id="d1", kind="data_json", module="stats", rel_path="d1.json"),
    ]
    selected = resolve_export_selection(
        arts,
        "Custom Selection",
        custom_ids=[],
        preselected_ids=["d1"],
    )
    assert {a.id for a in selected} == {"d1"}
