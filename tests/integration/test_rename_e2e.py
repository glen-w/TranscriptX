"""End-to-end rename: core pipeline + web service + slug index."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.core.utils.test_file_rename_contracts import _managed_old_name_transcript_env

pytestmark = pytest.mark.integration


def _register_slug_index(
    monkeypatch: pytest.MonkeyPatch,
    outputs: Path,
    transcript: Path,
    *,
    transcript_key: str = "sha256:testkey",
) -> None:
    from transcriptx.core.utils import slug_manager as sm

    index_file = outputs / ".transcriptx_index.json"
    monkeypatch.setattr(sm, "INDEX_FILE", index_file)
    index_file.write_text(
        json.dumps(
            {
                "transcripts": {
                    transcript_key: {
                        "slug": "old_name",
                        "runs": ["run_001"],
                        "source_basename": "old_name",
                        "source_path": str(transcript),
                    }
                },
                "slug_to_key": {"old_name": transcript_key},
            }
        ),
        encoding="utf-8",
    )


def test_rename_e2e_renames_artifacts_and_updates_slug_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_old_name_transcript_env(tmp_path, monkeypatch)
    transcript = env["transcript"]
    outputs = env["outputs"]
    recordings = env["recordings"]
    state_file = env["state_file"]

    old_audio = recordings / "old_name.mp3"
    old_audio.write_bytes(b"audio")
    state_file.write_text(
        json.dumps(
            {
                "processed_files": {
                    "u1": {
                        "transcript_path": str(transcript),
                        "mp3_path": str(old_audio),
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    _register_slug_index(monkeypatch, outputs, transcript)

    from transcriptx.web.services.rename_service import RenameService

    result = RenameService.rename_transcript_and_audio(transcript, "new_name")
    assert result.ok is True
    assert result.old_slug == "old_name"
    assert result.new_slug == "new_name"

    new_transcript = transcript.parent / "new_name.json"
    new_audio = recordings / "new_name.mp3"
    assert new_transcript.exists()
    assert not transcript.exists()
    assert new_audio.exists()
    assert not old_audio.exists()
    assert (outputs / "new_name").exists()
    assert not (outputs / "old_name").exists()

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["processed_files"]["u1"]["transcript_path"] == str(new_transcript)

    from transcriptx.core.utils import slug_manager as sm

    index = sm.load_index()
    entry = index["transcripts"]["sha256:testkey"]
    assert entry["slug"] == "new_name"
    assert entry["source_basename"] == "new_name"
    assert entry["source_path"] == str(new_transcript.resolve())
