"""Unit tests for export chart prep and transcript meta helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.export.chart_prep import (
    chart_kind_for_artifact,
    module_anchor_id,
    prepare_chart_export_view,
    sanitize_display_relpath,
)
from transcriptx.export.epub_xhtml import (
    provenance_meta_bits,
    slugify_chapter_id,
    xml_escape,
)
from transcriptx.export.transcript_meta import (
    format_transcript_meta_bits,
    transcript_export_meta,
)
from transcriptx.export.types import ExportableItem, TranscriptExportMeta
from transcriptx.web.models.artifact import Artifact


def _artifact(
    *,
    artifact_id: str,
    rel_path: str,
    kind: str,
    module: str | None = "sentiment",
    title: str | None = None,
    tags: list[str] | None = None,
) -> Artifact:
    return Artifact.from_dict(
        {
            "id": artifact_id,
            "kind": kind,
            "module": module,
            "scope": "global",
            "speaker": None,
            "subview": None,
            "slice_id": None,
            "rel_path": rel_path,
            "bytes": 0,
            "mtime": "2026-03-23T00:00:00Z",
            "mime": "image/png",
            "tags": tags or [],
            "title": title,
            "storage_root": None,
        }
    )


@pytest.mark.unit
def test_module_anchor_id_normalises_spaces_and_case() -> None:
    assert module_anchor_id("Key Themes") == "module-key-themes"
    assert module_anchor_id("STATS") == "module-stats"


@pytest.mark.unit
def test_chart_kind_for_artifact_static_vs_dynamic() -> None:
    assert chart_kind_for_artifact("chart_static") == "static"
    assert chart_kind_for_artifact("chart_dynamic") == "dynamic"
    assert chart_kind_for_artifact(None) == "dynamic"


@pytest.mark.unit
def test_sanitize_display_relpath_drive_and_dots() -> None:
    assert sanitize_display_relpath(r"C:\runs\chart.png") == "chart.png"
    assert sanitize_display_relpath("./mod/a.png") == "mod/a.png"
    assert sanitize_display_relpath(Path("charts/x.png")) == "charts/x.png"


@pytest.mark.unit
def test_prepare_chart_export_view_groups_and_orders(tmp_path: Path) -> None:
    a = _artifact(
        artifact_id="a",
        rel_path="zeta/a.png",
        kind="chart_static",
        module="Zeta",
        title="A",
    )
    b = _artifact(
        artifact_id="b",
        rel_path="alpha/b.png",
        kind="chart_dynamic",
        module="Alpha",
        title="B",
        tags=["x", "a"],
    )
    items = [
        ExportableItem(
            artifact=a,
            source_path=tmp_path / "zeta/a.png",
            export_rel_path=Path("zeta/a.png"),
            size_bytes=1,
        ),
        ExportableItem(
            artifact=b,
            source_path=tmp_path / "alpha/b.png",
            export_rel_path=Path("alpha/b.png"),
            size_bytes=1,
            description="from item",
        ),
    ]
    groups = prepare_chart_export_view(items)
    assert [g.module_name for g in groups] == ["Alpha", "Zeta"]
    assert groups[0].anchor_id == "module-alpha"
    assert groups[0].cards[0].kind == "dynamic"
    assert groups[0].cards[0].description == "from item"
    assert "a, x" in groups[0].cards[0].meta
    assert groups[1].cards[0].kind == "static"
    assert groups[1].cards[0].display_relpath == "zeta/a.png"


@pytest.mark.unit
def test_prepare_chart_export_view_description_fn_exception_is_ignored(
    tmp_path: Path,
) -> None:
    art = _artifact(
        artifact_id="c",
        rel_path="m/c.png",
        kind="chart_static",
        module="m",
    )
    item = ExportableItem(
        artifact=art,
        source_path=tmp_path / "m/c.png",
        export_rel_path=Path("m/c.png"),
        size_bytes=0,
    )

    def _boom(_artifact: object) -> str:
        raise RuntimeError("nope")

    groups = prepare_chart_export_view([item], description_fn=_boom)
    assert groups[0].cards[0].description is None


@pytest.mark.unit
def test_transcript_export_meta_speakers_and_duration_fallback() -> None:
    meta = transcript_export_meta(
        {
            "metadata": {"language": "en"},
            "segments": [
                {"speaker_display": "Alice", "speaker": "SPEAKER_0", "end": 1.0},
                {"speaker": "Bob", "end": 4.5},
                {"speaker_display": "Alice", "end": 2.0},
            ],
        }
    )
    assert meta.segment_count == 3
    assert meta.speakers == ("Alice", "Bob")
    assert meta.duration_seconds == pytest.approx(4.5)
    assert meta.language == "en"

    bad = transcript_export_meta(
        {"metadata": {}, "segments": [{"speaker": "A", "end": "bad"}]}
    )
    assert bad.duration_seconds is None


@pytest.mark.unit
def test_transcript_export_meta_invalid_duration_becomes_none() -> None:
    meta = transcript_export_meta(
        {"metadata": {"duration": "nope", "language": ""}, "segments": []}
    )
    assert meta.duration_seconds is None
    assert meta.language is None
    assert meta.segment_count == 0


@pytest.mark.unit
def test_format_transcript_meta_bits_includes_duration_and_language() -> None:
    bits = format_transcript_meta_bits(
        TranscriptExportMeta(
            segment_count=3,
            speakers=("A", "B"),
            duration_seconds=12.5,
            language="fr",
        )
    )
    assert bits[0] == "3 segments"
    assert bits[1] == "2 speakers"
    assert any(b.startswith("Duration ") for b in bits)
    assert "Language: fr" in bits


@pytest.mark.unit
def test_slugify_and_xml_escape_and_provenance_bits() -> None:
    assert slugify_chapter_id("Hello World!") == "hello-world"
    assert slugify_chapter_id("") == "section"
    assert slugify_chapter_id("9lives").startswith("s-")
    assert "&amp;" in xml_escape("A & B")
    assert "&quot;" in xml_escape('say "hi"')
    bits = provenance_meta_bits(
        {"model": "m1", "provider": "ollama", "truncated": True}
    )
    assert bits == ["Model: m1", "Provider: ollama", "Input truncated"]
    assert provenance_meta_bits(None) == []
