"""Theme F library_kind on the import sidecar."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.app.corpus_inventory.models import InventoryRow, LibraryFilter
from transcriptx.app.corpus_inventory.query import apply_library_filter
from transcriptx.io.import_metadata.schema import build_initial_sidecar
from transcriptx.io.tag_validation import LIBRARY_KIND_VALUES


@pytest.mark.unit
def test_kind_vocabulary() -> None:
    assert "meeting" in LIBRARY_KIND_VALUES
    assert "voice note" in LIBRARY_KIND_VALUES
    assert "lone speaker" in LIBRARY_KIND_VALUES


@pytest.mark.unit
def test_filter_by_kind() -> None:
    def row(kind: str | None, name: str) -> InventoryRow:
        from transcriptx.app.corpus_inventory.models import (
            AnalysisState,
            CorrectionsState,
            FieldIntegrity,
            SpeakerIdState,
            SpeakerIdStatus,
            CorrectionsStatus,
            AnalysisStatus,
        )

        return InventoryRow(
            transcript_path=Path(f"/{name}.json"),
            transcript_key=name,
            slug=name,
            title=name,
            imported_at=None,
            duration_seconds=1.0,
            speaker_count=1,
            word_count=1,
            source_id=None,
            listing_integrity=FieldIntegrity.OK,
            speaker=SpeakerIdState(
                status=SpeakerIdStatus.NONE, integrity=FieldIntegrity.OK
            ),
            corrections=CorrectionsState(
                status=CorrectionsStatus.NEVER_STARTED, integrity=FieldIntegrity.OK
            ),
            analysis=AnalysisState(
                status=AnalysisStatus.UNANALYSED, integrity=FieldIntegrity.OK
            ),
            last_activity_at=None,
            library_kind=kind,
        )

    rows = [row("meeting", "a"), row("voice note", "b"), row(None, "c")]
    filtered = apply_library_filter(rows, LibraryFilter(library_kind="meeting"))
    assert [r.title for r in filtered] == ["a"]


@pytest.mark.unit
def test_initial_sidecar_omits_kind() -> None:
    payload = build_initial_sidecar(
        import_id="i",
        imported_at="t",
        adapter_source_id="s",
        source_upload_basename="f.json",
        archived_original_relpath="originals/f.json",
        current_json_filename="f.json",
    )
    assert "library_kind" not in payload
