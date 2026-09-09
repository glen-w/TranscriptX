"""Tests for library-by-tag export resolution and ZIP packaging."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from transcriptx.app.corpus_inventory.models import (
    AnalysisState,
    AnalysisStatus,
    CorrectionsState,
    CorrectionsStatus,
    FieldIntegrity,
    FileStamp,
    InventoryFingerprint,
    InventoryRow,
    SpeakerIdState,
    SpeakerIdStatus,
)
from transcriptx.export.library_by_tag import (
    build_library_export_manifest,
    resolve_library_export_items,
)
from transcriptx.export.types import HARD_CAP_BYTES
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services.export_service import ExportService


def _fp() -> InventoryFingerprint:
    return InventoryFingerprint(stamps=(FileStamp("/x", 0, -1),))


def _row(
    tmp_path: Path,
    name: str,
    *,
    run_id: str | None = "run1",
    tags: tuple[str, ...] = ("meeting",),
) -> InventoryRow:
    transcript = tmp_path / f"{name}.json"
    transcript.write_text(json.dumps({"segments": []}), encoding="utf-8")
    return InventoryRow(
        transcript_path=transcript,
        transcript_key=name,
        slug=name,
        title=name,
        imported_at=None,
        duration_seconds=10.0,
        speaker_count=1,
        word_count=5,
        source_id=None,
        listing_integrity=FieldIntegrity.OK,
        speaker=SpeakerIdState(
            status=SpeakerIdStatus.COMPLETE, integrity=FieldIntegrity.OK
        ),
        corrections=CorrectionsState(
            status=CorrectionsStatus.NEVER_STARTED, integrity=FieldIntegrity.MISSING
        ),
        analysis=AnalysisState(
            status=AnalysisStatus.COMPLETED,
            integrity=FieldIntegrity.OK,
            latest_run_id=run_id,
            modules_succeeded=1,
            modules_eligible=1,
            last_analysed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        ),
        last_activity_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        tags=tags,
        fingerprint=_fp(),
    )


def _artifact(**kwargs) -> Artifact:
    base = {
        "id": "art1",
        "kind": "transcript",
        "module": None,
        "scope": None,
        "speaker": None,
        "subview": None,
        "slice_id": None,
        "rel_path": "transcripts/demo-transcript.txt",
        "bytes": 4,
        "mtime": "2026-09-01T00:00:00Z",
        "mime": "text/plain",
        "tags": [],
    }
    base.update(kwargs)
    return Artifact.from_dict(base)


def test_resolve_readable_and_json_kinds(tmp_path: Path, monkeypatch) -> None:
    outputs = tmp_path / "outputs"
    row = _row(tmp_path, "alpha")
    run_dir = outputs / "alpha" / "run1"
    txt = run_dir / "transcripts" / "alpha-transcript.txt"
    csv = run_dir / "transcripts" / "alpha-transcript.csv"
    txt.parent.mkdir(parents=True)
    txt.write_text("hello", encoding="utf-8")
    csv.write_text("a,b\n", encoding="utf-8")

    artifacts = [
        _artifact(
            id="t1",
            rel_path="transcripts/alpha-transcript.txt",
            bytes=5,
        ),
        _artifact(
            id="t2",
            kind="transcript",
            rel_path="transcripts/alpha-transcript.csv",
            bytes=4,
            mime="text/csv",
        ),
        _artifact(
            id="sum",
            kind="data_json",
            module="llm_summary",
            rel_path="llm_summary/global/alpha_llm_summary.json",
            bytes=2,
        ),
    ]
    monkeypatch.setattr(
        "transcriptx.web.services.artifact_service.ArtifactService.list_artifacts",
        staticmethod(lambda _run: artifacts),
    )
    monkeypatch.setattr(
        "transcriptx.web.services.artifact_service.ArtifactService.resolve_artifact_source_path",
        staticmethod(
            lambda run_root, artifact: run_root / artifact.rel_path
            if (run_root / artifact.rel_path).exists()
            else None
        ),
    )

    resolved = resolve_library_export_items(
        [row],
        ["readable_txt", "readable_csv", "transcript_json", "summaries"],
        outputs_dir=outputs,
    )
    assert resolved.matching_rows == 1
    assert resolved.included_rows == 1
    assert resolved.skipped_rows == 0
    kinds = {item.kind for item in resolved.items}
    assert "readable_txt" in kinds
    assert "readable_csv" in kinds
    assert "transcript_json" in kinds
    # summary artifact path does not exist on disk → not copied
    dests = [item.dest_rel.as_posix() for item in resolved.items]
    assert any(d.startswith("alpha/") for d in dests)
    assert any(d.endswith(".json") for d in dests)


def test_resolve_skips_rows_without_selected_kinds(tmp_path: Path, monkeypatch) -> None:
    outputs = tmp_path / "outputs"
    row = _row(tmp_path, "beta", run_id=None)
    monkeypatch.setattr(
        "transcriptx.web.services.artifact_service.ArtifactService.list_artifacts",
        staticmethod(lambda _run: []),
    )
    resolved = resolve_library_export_items(
        [row], ["readable_txt"], outputs_dir=outputs
    )
    assert resolved.included_rows == 0
    assert resolved.skipped_rows == 1


def test_zip_library_selection_layout_and_manifest(tmp_path: Path) -> None:
    from transcriptx.export.library_by_tag import LibraryExportItem

    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("aaa", encoding="utf-8")
    b.write_text("bbb", encoding="utf-8")
    items = [
        LibraryExportItem(
            src=a, dest_rel=Path("alpha/a.txt"), kind="readable_txt", transcript_slug="alpha"
        ),
        LibraryExportItem(
            src=b, dest_rel=Path("beta/b.txt"), kind="readable_txt", transcript_slug="beta"
        ),
    ]
    manifest = build_library_export_manifest(
        tags=["meeting"],
        kinds=["readable_txt"],
        items=items,
        matching_rows=2,
        included_rows=2,
        skipped_rows=0,
    )
    zip_path = ExportService.zip_library_selection(
        items, zip_basename="library_tag_export", manifest=manifest
    )
    assert zip_path is not None
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        assert "alpha/a.txt" in names
        assert "beta/b.txt" in names
        assert "manifest.json" in names
        assert "index.html" not in names
        assert "index.epub" not in names
        payload = json.loads(zf.read("manifest.json"))
        assert payload["manifest_type"] == "library_tag_export"
        assert payload["tags"] == ["meeting"]


def test_zip_library_selection_empty_returns_none() -> None:
    assert ExportService.zip_library_selection([]) is None


def test_zip_library_selection_hard_cap(tmp_path: Path, monkeypatch) -> None:
    from transcriptx.export.library_by_tag import LibraryExportItem

    huge = tmp_path / "huge.bin"
    huge.write_bytes(b"x" * 64)

    def boom(total_bytes: int, *, hard_cap: int = HARD_CAP_BYTES) -> None:
        raise ValueError("Export exceeds hard cap.")

    monkeypatch.setattr(
        "transcriptx.export.zipping.assert_under_hard_cap", boom
    )
    items = [
        LibraryExportItem(
            src=huge,
            dest_rel=Path("slug/huge.bin"),
            kind="data",
            transcript_slug="slug",
        )
    ]
    with pytest.raises(ValueError, match="hard cap"):
        ExportService.zip_library_selection(items)
