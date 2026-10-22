"""Unit tests for import_metadata persist/layout edges (0.3.7 package split)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.io.import_metadata.layout import (
    ImportSidecarLayout,
    resolve_import_sidecar_layout,
)
from transcriptx.io.import_metadata.persist import (
    append_rename_history,
    compute_rename_history_payload,
    load_sidecar,
    write_initial_sidecar,
)


@pytest.mark.unit
def test_load_sidecar_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="object"):
        load_sidecar(path)


@pytest.mark.unit
def test_compute_and_append_rename_history(tmp_path: Path, monkeypatch) -> None:
    transcripts = tmp_path / "transcripts"
    metadata = tmp_path / "metadata"
    transcripts.mkdir()
    metadata.mkdir()
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR", transcripts
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata
    )
    t = transcripts / "meet.json"
    t.write_text("{}", encoding="utf-8")
    sidecar = write_initial_sidecar(
        t,
        import_id="imp-1",
        imported_at="2026-01-01T00:00:00Z",
        adapter_source_id="manual",
        source_upload_basename="meet.json",
        archived_original_relpath="originals/meet.json",
    )
    mutated = compute_rename_history_payload(
        sidecar,
        old_filename="meet.json",
        new_filename="renamed.json",
        at_iso="2026-01-02T00:00:00Z",
    )
    assert mutated["current_json_filename"] == "renamed.json"
    assert mutated["rename_history"][-1]["to_filename"] == "renamed.json"

    append_rename_history(
        sidecar_path=sidecar,
        old_filename="meet.json",
        new_filename="renamed.json",
        at_iso="2026-01-02T00:00:00Z",
    )
    stored = load_sidecar(sidecar)
    assert stored["current_json_filename"] == "renamed.json"
    assert len(stored["rename_history"]) == 1


@pytest.mark.unit
def test_compute_rename_history_requires_list(tmp_path: Path) -> None:
    path = tmp_path / "side.json"
    path.write_text(json.dumps({"rename_history": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="rename_history"):
        compute_rename_history_payload(
            path,
            old_filename="a.json",
            new_filename="b.json",
            at_iso="2026-01-01T00:00:00Z",
        )


@pytest.mark.unit
def test_resolve_import_sidecar_layout_oserror_compare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    metadata = tmp_path / "metadata"
    transcripts.mkdir()
    metadata.mkdir()
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR", transcripts
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata
    )
    t = transcripts / "meet.json"
    t.write_text("{}", encoding="utf-8")

    from transcriptx.io.import_metadata_sidecar import (
        legacy_flat_sidecar_path_for_transcript,
        mirrored_import_sidecar_path_for_transcript,
    )

    mirrored = mirrored_import_sidecar_path_for_transcript(t)
    legacy = legacy_flat_sidecar_path_for_transcript(t)
    mirrored.parent.mkdir(parents=True, exist_ok=True)
    mirrored.write_text('{"a":1}', encoding="utf-8")
    legacy.write_text('{"a":1}', encoding="utf-8")

    real_read = Path.read_bytes

    def _boom(self: Path) -> bytes:
        if self == mirrored:
            raise OSError("permission denied")
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", _boom)
    resolved = resolve_import_sidecar_layout(t)
    assert resolved.layout == ImportSidecarLayout.ambiguous
    assert "Could not compare" in resolved.block_message


@pytest.mark.unit
def test_library_archived_round_trip(tmp_path: Path, monkeypatch) -> None:
    from transcriptx.io.import_metadata.persist import (
        is_library_archived,
        set_library_archived,
    )

    transcripts = tmp_path / "transcripts"
    metadata = tmp_path / "metadata"
    transcripts.mkdir()
    metadata.mkdir()
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR", transcripts
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata
    )
    t = transcripts / "meet.json"
    t.write_text("{}", encoding="utf-8")
    sidecar = write_initial_sidecar(
        t,
        import_id="imp-1",
        imported_at="2026-01-01T00:00:00Z",
        adapter_source_id="manual",
        source_upload_basename="meet.json",
        archived_original_relpath="originals/meet.json",
    )
    stored = load_sidecar(sidecar)
    assert stored["library_archived"] is False
    assert is_library_archived(t) is False

    set_library_archived(t, True)
    assert load_sidecar(sidecar)["library_archived"] is True
    assert is_library_archived(t) is True

    set_library_archived(t, False)
    assert is_library_archived(t) is False


@pytest.mark.unit
def test_is_library_archived_false_when_sidecar_missing(tmp_path: Path) -> None:
    from transcriptx.io.import_metadata.persist import is_library_archived

    assert is_library_archived(tmp_path / "nope.json") is False


@pytest.mark.unit
def test_set_library_archived_requires_sidecar(tmp_path: Path) -> None:
    from transcriptx.io.import_metadata.persist import set_library_archived

    with pytest.raises(FileNotFoundError, match="No import sidecar"):
        set_library_archived(tmp_path / "nope.json", True)
