"""Forward-compat: epoch-1 data roots from 0.9.7 open unchanged under current code."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.utils.schema_epoch import (
    CURRENT_SCHEMA_EPOCH,
    MARKER_FILENAME,
    MARKER_KIND,
    DataRootStatus,
    assess_data_root,
    ensure_epoch_marker,
    read_epoch,
    require_compatible_data_root,
)


def _write_097_style_epoch1_root(root: Path) -> Path:
    """Create a minimal epoch-1 store shaped like a 0.9.7 managed data root."""
    root.mkdir(parents=True, exist_ok=True)
    marker = {
        "kind": MARKER_KIND,
        "schema_epoch": 1,
    }
    (root / MARKER_FILENAME).write_text(
        json.dumps(marker, indent=2) + "\n", encoding="utf-8"
    )
    transcripts = root / "transcripts"
    transcripts.mkdir()
    sample = {
        "schema_version": 1,
        "segments": [
            {"start": 0.0, "end": 1.0, "text": "hello", "speaker": "A"},
        ],
    }
    (transcripts / "compatible_meeting.json").write_text(
        json.dumps(sample, indent=2) + "\n", encoding="utf-8"
    )
    recordings = root / "recordings"
    recordings.mkdir()
    (recordings / "compatible_meeting.wav").write_bytes(b"RIFF....WAVEfmt ")
    return root


def test_097_epoch1_root_opens_compatible_under_current(tmp_path: Path) -> None:
    assert CURRENT_SCHEMA_EPOCH == 1
    root = _write_097_style_epoch1_root(tmp_path / "data_097")
    assessment = assess_data_root(root)
    assert assessment.status == DataRootStatus.COMPATIBLE
    assert assessment.epoch == 1
    assert assessment.ok
    assert read_epoch(root) == 1

    ensured = ensure_epoch_marker(root)
    assert ensured.status == DataRootStatus.COMPATIBLE
    # Marker must not be rewritten away from epoch 1.
    payload = json.loads((root / MARKER_FILENAME).read_text(encoding="utf-8"))
    assert payload["schema_epoch"] == 1
    assert payload["kind"] == MARKER_KIND

    required = require_compatible_data_root(root)
    assert required.status == DataRootStatus.COMPATIBLE

    # Compatible transcript + recording retained (no wipe on open).
    assert (root / "transcripts" / "compatible_meeting.json").is_file()
    assert (root / "recordings" / "compatible_meeting.wav").is_file()
    transcript = json.loads(
        (root / "transcripts" / "compatible_meeting.json").read_text(encoding="utf-8")
    )
    assert transcript["schema_version"] == 1
