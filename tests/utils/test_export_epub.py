"""Tests for EPUB export planning, parity with HTML bundle, and isolation."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from transcriptx.export.bundle import (
    filter_copied_for_export_bundle,
    is_generated_presentation_artifact,
    resolve_export_bundle,
)
from transcriptx.export.chart_prep import (
    prepare_chart_export_view,
    sanitize_display_relpath,
)
from transcriptx.export.epub import (
    build_export_epub,
    plan_export_epub,
    resolve_static_image,
    write_epub_from_plan,
)
from transcriptx.export.epub_xhtml import ChapterIdAllocator, wrap_epub_xhtml
from transcriptx.export.index import build_export_index_html
from transcriptx.export.transcript_meta import transcript_export_meta
from transcriptx.export.types import (
    ChartExportCard,
    ChartModuleGroup,
    ExportableItem,
    ExportTextSummary,
)
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services.export_service import ExportService


def _artifact(
    *,
    artifact_id: str,
    rel_path: str,
    kind: str,
    module: str | None = "sentiment",
    title: str | None = None,
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
            "mime": "application/octet-stream",
            "tags": [],
            "title": title,
            "storage_root": None,
        }
    )


def _transcript() -> dict:
    return {
        "metadata": {"language": "en", "duration": 12.5},
        "segments": [
            {
                "speaker": "Alice",
                "text": "Hello there.",
                "start": 0.0,
                "end": 1.5,
            },
            {
                "speaker": "Bob",
                "text": "Hi Alice.",
                "start": 1.5,
                "end": 3.0,
            },
            {
                "speaker": "Αλίκη",
                "text": "Unicode speaker ✓",
                "start": 3.0,
                "end": 4.0,
            },
        ],
    }


def _png_bytes() -> bytes:
    # Minimal valid PNG (1x1)
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"
        b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_sanitize_display_relpath_strips_absolute() -> None:
    assert sanitize_display_relpath("/tmp/run/charts/a.png") == "a.png"
    assert sanitize_display_relpath("mod/charts/a.png") == "mod/charts/a.png"
    assert "../x" not in sanitize_display_relpath("../../secret/x.png")


def test_chapter_id_allocator_collisions() -> None:
    alloc = ChapterIdAllocator()
    a = alloc.allocate("summary-llm")
    b = alloc.allocate("summary-llm")
    assert a != b
    assert b.startswith("summary-llm")


def test_wrap_epub_xhtml_escapes_title() -> None:
    doc = wrap_epub_xhtml(title="A & B <C>", body="<p>x</p>")
    assert "&amp;" in doc
    assert "<C>" not in doc
    assert 'xmlns="http://www.w3.org/1999/xhtml"' in doc
    assert 'xmlns:epub="http://www.idpf.org/2007/ops"' in doc


def test_resolve_static_image_policy(tmp_path: Path) -> None:
    good = tmp_path / "a.png"
    good.write_bytes(_png_bytes())
    data, mime = resolve_static_image(good)
    assert mime == "image/png"
    assert data == _png_bytes()

    corrupt = tmp_path / "b.png"
    corrupt.write_bytes(b"not-a-png")
    assert resolve_static_image(corrupt) == (None, None)

    missing = tmp_path / "missing.png"
    assert resolve_static_image(missing) == (None, None)

    svg = tmp_path / "c.svg"
    svg.write_text("<svg></svg>", encoding="utf-8")
    assert resolve_static_image(svg) == (None, None)


def test_plan_export_epub_parity_fields(tmp_path: Path) -> None:
    png = tmp_path / "chart.png"
    png.write_bytes(_png_bytes())
    groups = (
        ChartModuleGroup(
            module_name="sentiment",
            anchor_id="module-sentiment",
            cards=(
                ChartExportCard(
                    title="Mood",
                    meta="sentiment · global · chart_static · —",
                    kind="static",
                    description="Static desc",
                    llm_description="Narrative text",
                    source_path=png,
                    export_rel_path=Path("sentiment/chart.png"),
                    display_relpath="sentiment/chart.png",
                ),
                ChartExportCard(
                    title="Interactive",
                    meta="sentiment · global · chart_dynamic · —",
                    kind="dynamic",
                    description="Dyn desc",
                    llm_description="Dyn narrative",
                    source_path=tmp_path / "x.html",
                    export_rel_path=Path("sentiment/x.html"),
                    display_relpath="sentiment/x.html",
                ),
            ),
        ),
    )
    summaries: list[ExportTextSummary] = [
        {
            "section_id": "summary-llm",
            "title": "LLM Transcript Summary",
            "body": "## Points\n\n- One\n- Two",
            "provenance": {
                "model": "test-model",
                "provider": "test-provider",
                "truncated": True,
            },
        },
        {
            "section_id": "summary-llm",  # collision
            "title": "Speaker Summary — Alice",
            "body": "Alice spoke briefly.",
            "provenance": {"model": "m2", "provider": "p2"},
        },
    ]
    plan = plan_export_epub(
        page_title="Run A",
        transcript_data=_transcript(),
        text_summaries=summaries,
        chart_groups=groups,
    )
    assert plan is not None
    titles = [c.title for c in plan.chapters]
    assert "Transcript" in titles
    assert "LLM Transcript Summary" in titles
    assert "Speaker Summary — Alice" in titles
    assert "sentiment" in titles

    transcript_xhtml = next(c.xhtml for c in plan.chapters if c.title == "Transcript")
    assert "Alice" in transcript_xhtml
    assert "Αλίκη" in transcript_xhtml

    summary_xhtml = next(
        c.xhtml for c in plan.chapters if c.title == "LLM Transcript Summary"
    )
    assert "Model: test-model" in summary_xhtml
    assert "Provider: test-provider" in summary_xhtml
    assert "Input truncated" in summary_xhtml

    chart_xhtml = next(c.xhtml for c in plan.chapters if c.title == "sentiment")
    assert "Static desc" in chart_xhtml
    assert "Narrative text" in chart_xhtml
    assert "images/" in chart_xhtml
    assert "Interactive HTML chart is not embeddable" in chart_xhtml
    assert "sentiment/x.html" in chart_xhtml
    assert str(tmp_path) not in chart_xhtml

    # Collision handling produced distinct chapter ids
    ids = [c.chapter_id for c in plan.chapters]
    assert len(ids) == len(set(ids))
    assert len(plan.images) == 1


def test_plan_empty_returns_none() -> None:
    assert plan_export_epub(page_title="Empty") is None


def test_section_isolation_bad_transcript_keeps_summary() -> None:
    plan = plan_export_epub(
        page_title="Partial",
        transcript_data={"segments": "not-a-list"},  # type: ignore[arg-type]
        text_summaries=[
            {
                "section_id": "s1",
                "title": "Summary",
                "body": "Still here.",
                "provenance": {},
            }
        ],
    )
    assert plan is not None
    titles = [c.title for c in plan.chapters]
    assert "Summary" in titles


def test_missing_static_chart_keeps_card_prose(tmp_path: Path) -> None:
    groups = (
        ChartModuleGroup(
            module_name="sentiment",
            anchor_id="module-sentiment",
            cards=(
                ChartExportCard(
                    title="Gone",
                    meta="sentiment · global · chart_static · —",
                    kind="static",
                    description="Still described",
                    llm_description="Still narrated",
                    source_path=tmp_path / "missing.png",
                    export_rel_path=Path("missing.png"),
                    display_relpath="missing.png",
                ),
            ),
        ),
    )
    plan = plan_export_epub(
        page_title="Missing img",
        transcript_data=_transcript(),
        chart_groups=groups,
    )
    assert plan is not None
    chart_xhtml = next(c.xhtml for c in plan.chapters if c.title == "sentiment")
    assert "Still described" in chart_xhtml
    assert "Still narrated" in chart_xhtml
    assert "unavailable" in chart_xhtml.lower() or "unsupported" in chart_xhtml.lower()
    assert plan.images == []


def test_long_transcript_plan_stays_valid() -> None:
    segments = [
        {
            "speaker": f"S{i % 3}",
            "text": ("word " * 40).strip() + f" #{i}",
            "start": float(i),
            "end": float(i) + 0.5,
        }
        for i in range(400)
    ]
    plan = plan_export_epub(
        page_title="Long",
        transcript_data={"metadata": {"language": "en"}, "segments": segments},
    )
    assert plan is not None
    transcript = next(c for c in plan.chapters if c.title == "Transcript")
    assert "#399" in transcript.xhtml
    assert 'xmlns="http://www.w3.org/1999/xhtml"' in transcript.xhtml


def test_build_export_epub_dependency_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import transcriptx.export.epub as epub_mod

    def _boom(_plan, _path):
        raise ImportError("ebooklib missing for test")

    monkeypatch.setattr(epub_mod, "write_epub_from_plan", _boom)
    out = build_export_epub(
        output_path=tmp_path / "index.epub",
        page_title="Dep",
        transcript_data=_transcript(),
    )
    assert out is None
    assert not (tmp_path / "index.epub").exists()


def test_build_export_epub_build_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import transcriptx.export.epub as epub_mod

    def _boom(_plan, _path):
        raise RuntimeError("packaging exploded")

    monkeypatch.setattr(epub_mod, "write_epub_from_plan", _boom)
    out = build_export_epub(
        output_path=tmp_path / "index.epub",
        page_title="Fail",
        transcript_data=_transcript(),
    )
    assert out is None


def test_charts_only_zip_has_no_epub(tmp_path: Path) -> None:
    from transcriptx.export.charts import prepare_charts_export_zip

    run_root = tmp_path / "run"
    png = run_root / "c.png"
    png.parent.mkdir(parents=True)
    png.write_bytes(_png_bytes())
    art = _artifact(
        artifact_id="c1",
        rel_path="c.png",
        kind="chart_static",
        title="C",
    )
    result = prepare_charts_export_zip(run_root, [art], "run")
    with zipfile.ZipFile(BytesIO(result.bytes)) as zf:
        names = set(zf.namelist())
    assert "index.html" in names
    assert "index.epub" not in names
    assert not any(n.endswith(".epub") for n in names)


def test_html_and_epub_share_bundle_content(tmp_path: Path) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    tpath = staging / "t.json"
    tpath.write_text(json.dumps(_transcript()), encoding="utf-8")
    png = staging / "a.png"
    png.write_bytes(_png_bytes())
    md = staging / "run_llm_summary.md"
    md.write_text("# Summary\n\nHello **world**.", encoding="utf-8")

    copied = [
        (
            _artifact(artifact_id="t1", rel_path="t.json", kind="transcript"),
            Path("t.json"),
        ),
        (
            _artifact(
                artifact_id="c1",
                rel_path="a.png",
                kind="chart_static",
                title="Chart A",
            ),
            Path("a.png"),
        ),
        (
            _artifact(
                artifact_id="s1",
                rel_path="run_llm_summary.md",
                kind="data",
                module="llm_summary",
                title="LLM Transcript Summary",
            ),
            Path("run_llm_summary.md"),
        ),
        (
            _artifact(
                artifact_id="epub1",
                rel_path="index.epub",
                kind="data",
            ),
            Path("index.epub"),
        ),
    ]
    (staging / "index.epub").write_bytes(b"PK fake")

    bundle = resolve_export_bundle(
        staging_dir=staging,
        run_title="run",
        copied=copied,
    )
    # Presentation artifact excluded from chart/summary/transcript inputs
    assert all(
        not is_generated_presentation_artifact(rel_path=c.export_rel_path)
        for c in bundle.chart_items
    )

    html = build_export_index_html(
        page_title=bundle.page_title,
        transcript_data=bundle.transcript_data,
        chart_groups=bundle.chart_groups,
        text_summaries=bundle.text_summaries,
    )
    plan = plan_export_epub(
        page_title=bundle.page_title,
        transcript_data=bundle.transcript_data,
        text_summaries=bundle.text_summaries,
        chart_groups=bundle.chart_groups,
    )
    assert html is not None and plan is not None
    assert "Alice" in html
    assert any("Alice" in c.xhtml for c in plan.chapters)
    assert "Hello there." in html
    assert any("Hello there." in c.xhtml for c in plan.chapters)

    meta = transcript_export_meta(bundle.transcript_data or {})
    assert meta.segment_count == 3
    assert "Alice" in meta.speakers


def test_filter_presentation_artifacts() -> None:
    copied = [
        (
            _artifact(artifact_id="a", rel_path="t.json", kind="transcript"),
            Path("t.json"),
        ),
        (
            _artifact(artifact_id="b", rel_path="index.html", kind="data"),
            Path("index.html"),
        ),
        (
            _artifact(artifact_id="c", rel_path="out.epub", kind="data"),
            Path("out.epub"),
        ),
    ]
    filtered = filter_copied_for_export_bundle(copied)
    assert len(filtered) == 1
    assert filtered[0][1].name == "t.json"


def test_write_epub_from_plan_integration(tmp_path: Path) -> None:
    ebooklib = pytest.importorskip("ebooklib")
    _ = ebooklib
    plan = plan_export_epub(
        page_title="Pack",
        transcript_data=_transcript(),
        text_summaries=[
            {
                "section_id": "s",
                "title": "Summary",
                "body": "Body text.",
                "provenance": {"model": "m"},
            }
        ],
    )
    assert plan is not None
    out = tmp_path / "index.epub"
    write_epub_from_plan(plan, out)
    assert out.is_file()
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "mimetype" in names
        assert "META-INF/container.xml" in names
        assert any(n.endswith(".xhtml") for n in names)


def test_zip_artifacts_includes_index_epub(tmp_path: Path) -> None:
    pytest.importorskip("ebooklib")
    run_root = tmp_path / "run"
    transcripts = run_root / "transcripts"
    transcripts.mkdir(parents=True)
    (transcripts / "t.json").write_text(json.dumps(_transcript()), encoding="utf-8")
    chart = run_root / "sentiment/charts/global/a.png"
    chart.parent.mkdir(parents=True)
    chart.write_bytes(_png_bytes())

    manifest = {
        "manifest_type": "artifact_manifest",
        "schema_version": 1,
        "run_id": "run",
        "artifacts": [
            {
                "id": "t1",
                "kind": "transcript",
                "rel_path": "transcripts/t.json",
                "bytes": 10,
                "mime": "application/json",
                "tags": [],
            },
            {
                "id": "c1",
                "kind": "chart_static",
                "module": "sentiment",
                "scope": "global",
                "rel_path": "sentiment/charts/global/a.png",
                "bytes": 3,
                "mime": "image/png",
                "tags": [],
            },
        ],
    }
    (run_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    zip_path = ExportService.zip_artifacts(run_root, ["t1", "c1"])
    assert zip_path is not None
    with zipfile.ZipFile(BytesIO(zip_path.read_bytes())) as zf:
        names = set(zf.namelist())
        assert "index.html" in names
        assert "index.epub" in names
