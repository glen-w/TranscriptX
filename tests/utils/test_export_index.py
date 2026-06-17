from __future__ import annotations

import json
from pathlib import Path

from transcriptx.utils.charts_export import _ExportableItem
from transcriptx.utils.export_index import (
    build_export_index_html,
    normalize_transcript_payload,
    render_transcript_section,
    resolve_export_llm_summary,
    resolve_export_page_title,
)
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services.artifact_service import ArtifactService


def _artifact(
    *,
    artifact_id: str,
    rel_path: str,
    kind: str,
    module: str | None = "sentiment",
    title: str | None = None,
    storage_root: str | None = None,
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
            "storage_root": storage_root,
        }
    )


def _transcript_data() -> dict:
    return {
        "metadata": {"language": "en"},
        "segments": [
            {"start": 0.0, "end": 2.5, "speaker": "SPEAKER_00", "text": "Hello there."},
            {
                "start": 2.5,
                "end": 5.0,
                "speaker": "SPEAKER_01",
                "text": "General Kenobi.",
            },
        ],
    }


def _chart_item(
    *, artifact_id: str, rel_path: str, kind: str = "chart_static", **kwargs
) -> _ExportableItem:
    return _ExportableItem(
        artifact=_artifact(
            artifact_id=artifact_id, rel_path=rel_path, kind=kind, **kwargs
        ),
        source_path=Path("/tmp") / rel_path,
        export_rel_path=Path(rel_path),
        size_bytes=0,
    )


def test_render_transcript_section_basic() -> None:
    html = render_transcript_section(_transcript_data())
    assert 'id="transcript"' in html
    assert "Hello there." in html
    assert "General Kenobi." in html
    assert "SPEAKER_00" in html
    assert "2 segments" in html
    assert "2 speakers" in html
    assert "Language: en" in html


def test_render_transcript_prefers_speaker_display() -> None:
    data = {
        "segments": [
            {
                "start": 0,
                "end": 1,
                "speaker": "SPEAKER_00",
                "speaker_display": "Alice",
                "text": "Hi",
            }
        ]
    }
    html = render_transcript_section(data)
    assert "Alice" in html
    assert "SPEAKER_00" not in html


def test_build_index_transcript_only() -> None:
    html = build_export_index_html(
        page_title="run-1", transcript_data=_transcript_data(), chart_items=[]
    )
    assert html is not None
    assert 'id="transcript"' in html
    assert "Hello there." in html
    assert 'class="card-grid"' not in html
    assert ">Transcript</a>" in html


def test_build_index_charts_only() -> None:
    items = [_chart_item(artifact_id="a", rel_path="sentiment/charts/global/a.png")]
    html = build_export_index_html(
        page_title="run-1", transcript_data=None, chart_items=items
    )
    assert html is not None
    assert 'id="transcript"' not in html
    assert 'src="sentiment/charts/global/a.png"' in html
    assert 'class="card-grid"' in html


def test_build_index_mixed_uses_posix_paths() -> None:
    items = [
        _chart_item(
            artifact_id="m",
            rel_path="0123456789abcdef/emotion/charts/global/b.png",
        )
    ]
    html = build_export_index_html(
        page_title="run-1", transcript_data=_transcript_data(), chart_items=items
    )
    assert html is not None
    assert 'id="transcript"' in html
    assert 'src="0123456789abcdef/emotion/charts/global/b.png"' in html
    assert "\\" not in html


def test_build_index_llm_summary_only() -> None:
    html = build_export_index_html(
        page_title="run-1",
        llm_summary={
            "section_id": "llm-summary",
            "title": "LLM Transcript Summary",
            "body": "A concise abstractive summary.",
            "provenance": {"model": "qwen3:8b", "provider": "ollama"},
        },
    )
    assert html is not None
    assert 'id="llm-summary"' in html
    assert "A concise abstractive summary." in html
    assert "qwen3:8b" in html
    assert ">LLM Transcript Summary</a>" in html


def test_build_index_mixed_includes_llm_summary() -> None:
    items = [_chart_item(artifact_id="a", rel_path="sentiment/charts/global/a.png")]
    html = build_export_index_html(
        page_title="run-1",
        transcript_data=_transcript_data(),
        chart_items=items,
        llm_summary={
            "section_id": "llm-summary",
            "title": "LLM Transcript Summary",
            "body": "Summary from the LLM.",
            "provenance": {},
        },
    )
    assert html is not None
    assert 'id="transcript"' in html
    assert "Summary from the LLM." in html
    assert 'class="card-grid"' in html


def test_resolve_export_llm_summary_prefers_json(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    (staging / "llm_summary/data/global").mkdir(parents=True)
    (staging / "llm_summary/data/global/demo_llm_summary.json").write_text(
        json.dumps(
            {
                "summary": "JSON summary body",
                "provenance": {"model": "qwen3:8b"},
            }
        ),
        encoding="utf-8",
    )
    (staging / "llm_summary/data/global/demo_llm_summary.md").write_text(
        "# Transcript Summary\n\nMarkdown body\n",
        encoding="utf-8",
    )
    copied = [
        (
            _artifact(
                artifact_id="j",
                rel_path="llm_summary/data/global/demo_llm_summary.json",
                kind="data_json",
                module="llm_summary",
            ),
            Path("llm_summary/data/global/demo_llm_summary.json"),
        ),
        (
            _artifact(
                artifact_id="m",
                rel_path="llm_summary/data/global/demo_llm_summary.md",
                kind="data_txt",
                module="llm_summary",
            ),
            Path("llm_summary/data/global/demo_llm_summary.md"),
        ),
    ]
    resolved = resolve_export_llm_summary(staging_dir=staging, copied=copied)
    assert resolved is not None
    assert resolved["body"] == "JSON summary body"
    assert resolved["provenance"]["model"] == "qwen3:8b"


def test_write_export_index_includes_llm_summary(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    (staging / "llm_summary/data/global").mkdir(parents=True)
    (staging / "llm_summary/data/global/demo_llm_summary.json").write_text(
        json.dumps({"summary": "Exported LLM summary", "provenance": {}}),
        encoding="utf-8",
    )
    copied = [
        (
            _artifact(
                artifact_id="j",
                rel_path="llm_summary/data/global/demo_llm_summary.json",
                kind="data_json",
                module="llm_summary",
            ),
            Path("llm_summary/data/global/demo_llm_summary.json"),
        ),
    ]
    html = _write_index(staging, copied)
    assert html is not None
    assert "Exported LLM summary" in html
    assert 'id="llm-summary"' in html


def test_build_index_neither_returns_none() -> None:
    assert build_export_index_html(page_title="run-1") is None
    assert (
        build_export_index_html(
            page_title="run-1", transcript_data=None, chart_items=[]
        )
        is None
    )


def test_build_index_escapes_dynamic_values() -> None:
    data = {
        "segments": [
            {
                "start": 0,
                "end": 1,
                "speaker": '<b>"Bob"&</b>',
                "text": "<script>alert(1)</script>",
            }
        ]
    }
    items = [
        _chart_item(
            artifact_id="x",
            rel_path="sentiment/charts/global/x.png",
            title='Chart <"&> Title',
        )
    ]
    html = build_export_index_html(
        page_title='Run <"&>', transcript_data=data, chart_items=items
    )
    assert html is not None
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert '<b>"Bob"&</b>' not in html
    assert "Run &lt;" in html
    assert "Chart &lt;" in html


def test_build_index_included_files_footer() -> None:
    html = build_export_index_html(
        page_title="run-1",
        transcript_data=_transcript_data(),
        included_files=["transcripts/a.json", "report.json"],
    )
    assert html is not None
    assert "Included files" in html
    assert "transcripts/a.json" in html
    assert "report.json" in html


def _write_index(
    staging_dir: Path, copied: list[tuple[Artifact, Path]], title: str = "run"
) -> str | None:
    ArtifactService._write_export_index(staging_dir, title, copied)
    index = staging_dir / "index.html"
    return index.read_text(encoding="utf-8") if index.exists() else None


def test_write_export_index_malformed_transcript_keeps_charts(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging"
    (staging / "transcripts").mkdir(parents=True)
    (staging / "transcripts/t.json").write_text("{not valid json", encoding="utf-8")
    (staging / "sentiment/charts/global").mkdir(parents=True)
    (staging / "sentiment/charts/global/a.png").write_bytes(b"png")

    copied = [
        (
            _artifact(
                artifact_id="t",
                rel_path="transcripts/t.json",
                kind="transcript",
                module=None,
            ),
            Path("transcripts/t.json"),
        ),
        (
            _artifact(
                artifact_id="c",
                rel_path="sentiment/charts/global/a.png",
                kind="chart_static",
            ),
            Path("sentiment/charts/global/a.png"),
        ),
    ]
    html = _write_index(staging, copied)
    assert html is not None
    assert 'class="card-grid"' in html
    assert 'src="sentiment/charts/global/a.png"' in html
    assert 'id="transcript"' not in html


def test_write_export_index_prefers_transcript_with_segments(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    (staging / "transcripts").mkdir(parents=True)
    summary = {"total_original": 10, "total_simplified": 8, "removed_count": 2}
    full = {
        "segments": [{"start": 0, "end": 1, "speaker": "Alice", "text": "hello world"}]
    }
    (staging / "transcripts/summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )
    (staging / "transcripts/full.json").write_text(json.dumps(full), encoding="utf-8")

    copied = [
        (
            _artifact(
                artifact_id="1",
                rel_path="transcripts/summary.json",
                kind="transcript",
                module=None,
            ),
            Path("transcripts/summary.json"),
        ),
        (
            _artifact(
                artifact_id="2",
                rel_path="transcripts/full.json",
                kind="transcript",
                module=None,
            ),
            Path("transcripts/full.json"),
        ),
    ]
    html = _write_index(staging, copied)
    assert html is not None
    assert "hello world" in html
    assert "1 segments" in html


def test_write_export_index_first_transcript_in_selected_order(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging"
    (staging / "transcripts").mkdir(parents=True)
    first = {"segments": [{"start": 0, "end": 1, "speaker": "Alice", "text": "hi"}]}
    second = {"segments": [{"start": 0, "end": 1, "speaker": "Bob", "text": "yo"}]}
    (staging / "transcripts/first.json").write_text(json.dumps(first), encoding="utf-8")
    (staging / "transcripts/second.json").write_text(
        json.dumps(second), encoding="utf-8"
    )

    copied = [
        (
            _artifact(
                artifact_id="1",
                rel_path="transcripts/first.json",
                kind="transcript",
                module=None,
            ),
            Path("transcripts/first.json"),
        ),
        (
            _artifact(
                artifact_id="2",
                rel_path="transcripts/second.json",
                kind="transcript",
                module=None,
            ),
            Path("transcripts/second.json"),
        ),
    ]
    html = _write_index(staging, copied)
    assert html is not None
    assert "Alice" in html
    assert "Bob" not in html


def test_normalize_transcript_payload_accepts_simplified_list() -> None:
    payload = normalize_transcript_payload(
        [{"speaker": "Alice", "text": "Hello"}, {"speaker": "Bob", "text": "Hi"}]
    )
    assert payload is not None
    assert len(payload["segments"]) == 2


def test_resolve_export_page_title_from_report(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    (run_root / "report.json").write_text(
        json.dumps({"meta": {"base_name": "my_transcript"}}),
        encoding="utf-8",
    )
    title = resolve_export_page_title(
        staging_dir=run_root, run_root=run_root, fallback="run-id"
    )
    assert title == "my_transcript"


def test_write_export_index_uses_enriched_transcript_fallback(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    (staging / "transcripts").mkdir(parents=True)
    (staging / "transcripts/summary.json").write_text(
        json.dumps({"total_original": 1}), encoding="utf-8"
    )
    (staging / "sentiment/data/global").mkdir(parents=True)
    enriched = {
        "segments": [
            {"start": 0, "end": 1, "speaker": "Alice", "text": "from sentiment"}
        ]
    }
    (staging / "sentiment/data/global/demo_with_sentiment.json").write_text(
        json.dumps(enriched), encoding="utf-8"
    )

    copied = [
        (
            _artifact(
                artifact_id="s",
                rel_path="transcripts/summary.json",
                kind="transcript",
                module=None,
            ),
            Path("transcripts/summary.json"),
        ),
        (
            _artifact(
                artifact_id="d",
                rel_path="sentiment/data/global/demo_with_sentiment.json",
                kind="data_json",
                module="sentiment",
            ),
            Path("sentiment/data/global/demo_with_sentiment.json"),
        ),
    ]
    html = _write_index(staging, copied)
    assert html is not None
    assert "from sentiment" in html


def test_write_export_index_neither_writes_nothing(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "data.json").write_text("{}", encoding="utf-8")
    copied = [
        (
            _artifact(
                artifact_id="d",
                rel_path="data.json",
                kind="data_json",
                module=None,
            ),
            Path("data.json"),
        )
    ]
    html = _write_index(staging, copied)
    assert html is None


def test_zip_artifacts_includes_index_html(tmp_path: Path) -> None:
    import zipfile
    from io import BytesIO

    run_root = tmp_path / "run"
    transcripts = run_root / "transcripts"
    transcripts.mkdir(parents=True)
    (transcripts / "t.json").write_text(
        json.dumps(_transcript_data()), encoding="utf-8"
    )
    chart = run_root / "sentiment/charts/global/a.png"
    chart.parent.mkdir(parents=True)
    chart.write_bytes(b"png")

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

    zip_path = ArtifactService.zip_artifacts(run_root, ["t1", "c1"])
    assert zip_path is not None
    with zipfile.ZipFile(BytesIO(zip_path.read_bytes())) as zf:
        names = set(zf.namelist())
        assert "index.html" in names
        assert "transcripts/t.json" in names
        assert "sentiment/charts/global/a.png" in names
        index_html = zf.read("index.html").decode("utf-8")
    assert 'id="transcript"' in index_html
    assert "Hello there." in index_html
    assert 'class="card-grid"' in index_html
