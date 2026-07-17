"""Tests for ExportService ownership after export residual finish."""

from __future__ import annotations

import importlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from transcriptx.export import (
    normalize_transcript_payload,
    resolve_export_llm_summary,
    resolve_export_page_title,
    resolve_export_text_summaries,
    resolve_export_transcript_data,
)
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services.artifact_service import ArtifactService
from transcriptx.web.services.export_service import ExportService


def _artifact(**kwargs) -> Artifact:
    base = {
        "id": "a1",
        "kind": "chart_static",
        "module": "sentiment",
        "scope": "global",
        "speaker": None,
        "subview": None,
        "slice_id": None,
        "rel_path": "sentiment/charts/global/a.png",
        "bytes": 3,
        "mtime": "2026-03-23T00:00:00Z",
        "mime": "image/png",
        "tags": [],
    }
    base.update(kwargs)
    return Artifact.from_dict(base)


@pytest.mark.unit
def test_artifact_service_no_longer_owns_zip_orchestration() -> None:
    assert not hasattr(ArtifactService, "zip_artifacts")
    assert not hasattr(ArtifactService, "_write_export_index")
    assert hasattr(ExportService, "zip_artifacts")
    assert hasattr(ExportService, "_write_export_index")
    assert hasattr(ExportService, "zip_charts")


@pytest.mark.unit
def test_utils_export_shims_removed() -> None:
    for mod in (
        "transcriptx.utils.export_index",
        "transcriptx.utils.export_markdown",
        "transcriptx.utils.charts_export",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod)


@pytest.mark.unit
def test_resolve_public_symbols_reexported_from_split_modules() -> None:
    from transcriptx.export import resolve as resolve_mod
    from transcriptx.export import resolve_summaries, resolve_transcript

    assert (
        resolve_mod.normalize_transcript_payload
        is resolve_transcript.normalize_transcript_payload
    )
    assert (
        resolve_mod.resolve_export_transcript_data
        is resolve_transcript.resolve_export_transcript_data
    )
    assert (
        resolve_mod.resolve_export_page_title
        is resolve_transcript.resolve_export_page_title
    )
    assert (
        resolve_mod.resolve_export_text_summaries
        is resolve_summaries.resolve_export_text_summaries
    )
    assert (
        resolve_mod.resolve_export_llm_summary
        is resolve_summaries.resolve_export_llm_summary
    )
    # Package-level imports stay usable after the split.
    assert callable(normalize_transcript_payload)
    assert callable(resolve_export_transcript_data)
    assert callable(resolve_export_page_title)
    assert callable(resolve_export_text_summaries)
    assert callable(resolve_export_llm_summary)


@pytest.mark.unit
def test_zip_artifacts_empty_selection_returns_none(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    (run_root / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_type": "artifact_manifest",
                "schema_version": 1,
                "run_id": "run",
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    assert ExportService.zip_artifacts(run_root, ["missing"]) is None


@pytest.mark.unit
def test_zip_charts_uses_default_path_resolver(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    chart = run_root / "sentiment/charts/global/a.png"
    chart.parent.mkdir(parents=True)
    chart.write_bytes(b"png")
    artifact = _artifact(bytes=3)

    result = ExportService.zip_charts(run_root, [artifact], "run_charts")
    assert result.filename == "run_charts_charts.zip"
    assert result.exported_count == 1
    assert result.omitted_count == 0

    with zipfile.ZipFile(BytesIO(result.bytes)) as zf:
        names = set(zf.namelist())
        assert "index.html" in names
        assert "sentiment/charts/global/a.png" in names
        index_html = zf.read("index.html").decode("utf-8")
        assert "Charts Export" in index_html


@pytest.mark.unit
def test_write_export_index_owned_by_export_service(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    chart_dir = staging / "sentiment/charts/global"
    chart_dir.mkdir(parents=True)
    (chart_dir / "a.png").write_bytes(b"png")
    copied = [
        (
            _artifact(),
            Path("sentiment/charts/global/a.png"),
        )
    ]
    ExportService._write_export_index(staging, "run-title", copied)
    index = staging / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")
    assert "run-title" in html
    assert "sentiment/charts/global/a.png" in html
