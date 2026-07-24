"""Tests for schema-epoch remediation helpers."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.utils.schema_epoch import CURRENT_SCHEMA_EPOCH, read_epoch
from transcriptx.core.utils.schema_epoch_remediation import (
    create_fresh_data_directory,
    export_transcript_inventory,
    inventory_compatible_transcripts,
    reset_incompatible_derived_state,
)


def test_inventory_skips_sidecars(tmp_path: Path) -> None:
    root = tmp_path / "data"
    tdir = root / "transcripts"
    (tdir / "imports").mkdir(parents=True)
    (tdir / "meeting.json").write_text('{"schema_version": 1}\n', encoding="utf-8")
    (tdir / "meeting.speaker_map.json").write_text("{}\n", encoding="utf-8")
    meta = tdir / "metadata" / "imports"
    meta.mkdir(parents=True)
    (meta / "meeting.import_meta.json").write_text("{}\n", encoding="utf-8")

    inv = inventory_compatible_transcripts(root, transcripts_dir=tdir)
    assert inv.count == 1
    assert inv.items[0].relative_path == "meeting.json"


def test_export_inventory(tmp_path: Path) -> None:
    root = tmp_path / "data"
    tdir = root / "transcripts"
    tdir.mkdir(parents=True)
    (tdir / "a.json").write_text("{}\n", encoding="utf-8")
    inv = inventory_compatible_transcripts(root, transcripts_dir=tdir)
    out = tmp_path / "inv.json"
    export_transcript_inventory(inv, out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["count"] == 1
    assert payload["schema_epoch"] == CURRENT_SCHEMA_EPOCH


def test_create_fresh_data_directory(tmp_path: Path) -> None:
    fresh = tmp_path / "fresh_data"
    create_fresh_data_directory(fresh)
    assert read_epoch(fresh) == CURRENT_SCHEMA_EPOCH


def test_create_fresh_refuses_nonempty(tmp_path: Path) -> None:
    fresh = tmp_path / "fresh_data"
    fresh.mkdir()
    (fresh / "x").mkdir()
    try:
        create_fresh_data_directory(fresh)
        assert False, "expected FileExistsError"
    except FileExistsError:
        pass


def test_reset_derived_preserves_recordings_and_transcripts(tmp_path: Path) -> None:
    root = tmp_path / "data"
    rec = root / "recordings"
    tr = root / "transcripts"
    outputs = root / "outputs"
    cache = root / "cache"
    for d in (rec, tr, outputs, cache):
        d.mkdir(parents=True)
    (rec / "a.wav").write_bytes(b"RIFF")
    (tr / "meeting.json").write_text("{}\n", encoding="utf-8")
    (outputs / "run").mkdir()
    (cache / "x").mkdir()

    report = reset_incompatible_derived_state(
        root,
        recordings_dir=rec,
        transcripts_dir=tr,
        write_epoch_marker=True,
    )
    assert (rec / "a.wav").is_file()
    assert (tr / "meeting.json").is_file()
    assert not outputs.exists()
    assert not cache.exists()
    assert not report.recordings_touched
    assert not report.transcripts_touched
    assert str(outputs) in report.removed_paths
    assert read_epoch(root) == CURRENT_SCHEMA_EPOCH
    assert report.epoch_written
