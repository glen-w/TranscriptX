from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

import pytest

from transcriptx.utils.charts_export import (
    ChartsExportResult,
    _ExportableItem,
    _export_rel_path_for_chart,
    _resolve_exportable,
    generate_charts_index_html,
    prepare_charts_export_zip,
)
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services.artifact_service import ArtifactService


def _artifact(
    *,
    artifact_id: str,
    rel_path: str,
    kind: str = "chart_static",
    module: str | None = "sentiment",
    title: str | None = None,
    storage_root: str | None = None,
    bytes_size: int = 0,
    meta: dict | None = None,
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
            "bytes": bytes_size,
            "mtime": "2026-03-23T00:00:00Z",
            "mime": "image/png" if kind == "chart_static" else "text/html",
            "tags": [],
            "title": title,
            "storage_root": storage_root,
            "meta": meta,
        }
    )


def test_export_rel_path_for_chart_normal_and_group_member() -> None:
    normal = _artifact(artifact_id="abc123", rel_path="sentiment/charts/global/a.png")
    member = _artifact(
        artifact_id="0123456789abcdefZZ",
        rel_path="sentiment/charts/global/b.png",
        storage_root="/tmp/member",
    )
    assert _export_rel_path_for_chart(normal) == Path("sentiment/charts/global/a.png")
    assert _export_rel_path_for_chart(member) == Path("0123456789abcdef") / Path(
        "sentiment/charts/global/b.png"
    )


def test_resolve_artifact_source_path_valid_missing_and_traversal(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    img = run_root / "sentiment/charts/global/a.png"
    img.parent.mkdir(parents=True)
    img.write_bytes(b"png")

    valid = _artifact(artifact_id="1", rel_path="sentiment/charts/global/a.png")
    missing = _artifact(artifact_id="2", rel_path="sentiment/charts/global/missing.png")
    traversal = _artifact(artifact_id="3", rel_path="../outside.png")

    assert ArtifactService.resolve_artifact_source_path(run_root, valid) == img
    assert ArtifactService.resolve_artifact_source_path(run_root, missing) is None
    assert ArtifactService.resolve_artifact_source_path(run_root, traversal) is None


def test_resolve_exportable_prefers_stat_size_and_omits_missing(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    img = run_root / "sentiment/charts/global/a.png"
    img.parent.mkdir(parents=True)
    img.write_bytes(b"0123456789")

    ok = _artifact(
        artifact_id="ok",
        rel_path="sentiment/charts/global/a.png",
        bytes_size=1,  # stale metadata
    )
    missing = _artifact(
        artifact_id="missing",
        rel_path="sentiment/charts/global/does_not_exist.png",
        bytes_size=9999,
    )
    items = _resolve_exportable(run_root, [ok, missing])
    assert len(items) == 1
    assert items[0].artifact.id == "ok"
    assert items[0].size_bytes == 10


def test_generate_charts_index_html_structure_and_ordering() -> None:
    item_other = _ExportableItem(
        artifact=_artifact(
            artifact_id="a",
            rel_path="zmod/charts/global/z.png",
            module=None,
            title="Z Static",
        ),
        source_path=Path("/tmp/a"),
        export_rel_path=Path("zmod/charts/global/z.png"),
        size_bytes=10,
    )
    item_dyn = _ExportableItem(
        artifact=_artifact(
            artifact_id="b",
            rel_path="sentiment/charts/global/d.html",
            kind="chart_dynamic",
            module="sentiment",
            title="Dynamic",
        ),
        source_path=Path("/tmp/b"),
        export_rel_path=Path("sentiment/charts/global/d.html"),
        size_bytes=10,
    )
    html = generate_charts_index_html(
        [item_other, item_dyn],
        omitted_count=2,
        run_title="run-123",
    )
    assert "cdn.jsdelivr.net" not in html
    assert "<style>" in html
    assert "2 charts were unavailable and omitted" in html
    assert 'src="zmod/charts/global/z.png"' in html
    assert 'loading="lazy"' in html
    assert 'href="sentiment/charts/global/d.html"' in html
    assert "<iframe" in html
    assert "Interactive HTML" in html
    # Known taxonomy modules sort before unknown/Other sentinel buckets.
    assert html.index(">sentiment<") < html.index(">Other<")


def test_generate_charts_index_html_includes_visible_description() -> None:
    """A chart with a registry-backed viz_id renders a visible description caption."""
    item = _ExportableItem(
        artifact=_artifact(
            artifact_id="at",
            rel_path="affect_tension/charts/global/static/run_mismatch_heatmap.png",
            module="affect_tension",
            title="Mismatch Category Rates by Speaker",
            meta={"viz_id": "affect_tension.mismatch_heatmap.global"},
        ),
        source_path=Path("/tmp/at"),
        export_rel_path=Path(
            "affect_tension/charts/global/static/run_mismatch_heatmap.png"
        ),
        size_bytes=10,
    )
    html = generate_charts_index_html([item], omitted_count=0, run_title="run-x")
    assert '<p class="chart-desc">' in html
    assert '<span class="tx-info"' not in html


def test_generate_charts_index_html_omits_description_when_unknown() -> None:
    """A chart with no registry match renders no description paragraph."""
    item = _ExportableItem(
        artifact=_artifact(
            artifact_id="unk",
            rel_path="mystery/charts/global/static/unknown_chart.png",
            module="mystery",
            title="Unknown Chart",
            meta={"viz_id": "mystery.unknown.global"},
        ),
        source_path=Path("/tmp/unk"),
        export_rel_path=Path("mystery/charts/global/static/unknown_chart.png"),
        size_bytes=10,
    )
    html = generate_charts_index_html([item], omitted_count=0, run_title="run-y")
    assert '<p class="chart-desc">' not in html
    assert '<span class="tx-info"' not in html


def test_prepare_charts_export_zip_contents_and_member_prefix(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()

    static_file = run_root / "sentiment/charts/global/a.png"
    static_file.parent.mkdir(parents=True)
    static_file.write_bytes(b"static")

    member_root = tmp_path / "member"
    member_file = member_root / "emotion/charts/global/b.html"
    member_file.parent.mkdir(parents=True)
    member_file.write_text("<html>member</html>", encoding="utf-8")

    static_artifact = _artifact(
        artifact_id="st",
        rel_path="sentiment/charts/global/a.png",
        module="sentiment",
    )
    member_artifact = _artifact(
        artifact_id="0123456789abcdefx",
        rel_path="emotion/charts/global/b.html",
        kind="chart_dynamic",
        module="emotion",
        storage_root=str(member_root),
    )

    result = prepare_charts_export_zip(
        run_root,
        [static_artifact, member_artifact],
        "run_1",
    )
    assert result.filename == "run_1_charts.zip"
    assert result.exported_count == 2
    assert result.omitted_count == 0
    assert result.module_count == 2

    with zipfile.ZipFile(BytesIO(result.bytes)) as zf:
        names = set(zf.namelist())
        assert "index.html" in names
        assert "sentiment/charts/global/a.png" in names
        assert "0123456789abcdef/emotion/charts/global/b.html" in names


def test_prepare_charts_export_zip_missing_is_omitted(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    ok_file = run_root / "sentiment/charts/global/a.png"
    ok_file.parent.mkdir(parents=True)
    ok_file.write_bytes(b"ok")

    ok = _artifact(artifact_id="ok", rel_path="sentiment/charts/global/a.png")
    missing = _artifact(artifact_id="missing", rel_path="sentiment/charts/global/m.png")

    result = prepare_charts_export_zip(run_root, [ok, missing], "run_2")
    assert result.exported_count == 1
    assert result.omitted_count == 1

    with zipfile.ZipFile(BytesIO(result.bytes)) as zf:
        names = set(zf.namelist())
        assert "sentiment/charts/global/a.png" in names
        assert "sentiment/charts/global/m.png" not in names


def test_prepare_charts_export_zip_size_cap_raises_before_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    big = run_root / "sentiment/charts/global/a.png"
    big.parent.mkdir(parents=True)
    big.write_bytes(b"X" * 20)
    artifact = _artifact(artifact_id="big", rel_path="sentiment/charts/global/a.png")

    import transcriptx.utils.charts_export as charts_export

    monkeypatch.setattr(charts_export, "HARD_CAP_BYTES", 5)
    called = {"copy": False}

    def _copy_spy(*args, **kwargs):
        called["copy"] = True
        return None

    monkeypatch.setattr(charts_export.shutil, "copy2", _copy_spy)
    with pytest.raises(ValueError, match="hard cap"):
        prepare_charts_export_zip(run_root, [artifact], "run_3")
    assert called["copy"] is False


def test_prepare_charts_export_zip_temp_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    chart = run_root / "sentiment/charts/global/a.png"
    chart.parent.mkdir(parents=True)
    chart.write_bytes(b"abc")
    artifact = _artifact(artifact_id="a1", rel_path="sentiment/charts/global/a.png")

    staging_dir = tmp_path / "staging"
    zip_dir = tmp_path / "ziptmp"
    paths = iter([str(staging_dir), str(zip_dir)])

    import transcriptx.utils.charts_export as charts_export

    monkeypatch.setattr(
        charts_export.tempfile, "mkdtemp", lambda prefix="": next(paths)
    )
    result = prepare_charts_export_zip(run_root, [artifact], "run_4")
    assert result.bytes
    assert not staging_dir.exists()
    assert not zip_dir.exists()


def test_export_signature_and_staleness_guard() -> None:
    one = _artifact(artifact_id="1", rel_path="sentiment/charts/global/a.png")
    two = _artifact(artifact_id="2", rel_path="sentiment/charts/global/b.png")
    sig_a = frozenset(a.id for a in [one, two])
    sig_b = frozenset(a.id for a in [one])
    result = ChartsExportResult(
        bytes=b"zip",
        filename="run.zip",
        exported_count=2,
        omitted_count=0,
        module_count=1,
    )

    # Model the same staleness rule used by charts.py without importing Streamlit page code.
    def _has_current_export_local(
        stored_result: object, stored_sig: object, current_sig: frozenset[str]
    ) -> bool:
        return (
            isinstance(stored_result, ChartsExportResult) and stored_sig == current_sig
        )

    assert _has_current_export_local(result, sig_a, sig_a) is True
    assert _has_current_export_local(result, sig_a, sig_b) is False
    assert _has_current_export_local(None, sig_a, sig_a) is False
