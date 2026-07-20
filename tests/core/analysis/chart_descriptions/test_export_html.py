"""Export HTML includes registry + LLM narratives."""

from __future__ import annotations

from pathlib import Path

from transcriptx.export.charts import render_chart_sections
from transcriptx.export.types import ExportableItem
from transcriptx.web.models.artifact import Artifact


def test_export_renders_both_descriptions_under_and_above():
    artifact = Artifact(
        id="abc123",
        kind="chart_static",
        module="stats",
        scope="global",
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path="stats/charts/x.png",
        bytes=10,
        mtime="2020-01-01T00:00:00Z",
        mime="image/png",
        tags=[],
        title="Demo",
    )
    item = ExportableItem(
        artifact=artifact,
        source_path=Path("/tmp/x.png"),
        export_rel_path=Path("stats/charts/x.png"),
        size_bytes=10,
        description="Registry help text",
        llm_description='Narrative with <script>alert("x")</script>',
    )
    _toc, sections = render_chart_sections([item])
    html = "".join(sections)
    assert "Registry help text" in html
    assert "chart-desc" in html
    assert "chart-narrative" in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    # Narrative appears after image body marker (img tag)
    assert html.index("chart-desc") < html.index("<img")
    assert html.index("<img") < html.index("chart-narrative")
