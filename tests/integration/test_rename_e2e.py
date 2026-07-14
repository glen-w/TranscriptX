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
    slug: str = "old_name",
    extra_entries: dict | None = None,
) -> Path:
    from transcriptx.core.utils import slug_manager as sm

    index_file = outputs / ".transcriptx_index.json"
    monkeypatch.setattr(sm, "INDEX_FILE", index_file)
    monkeypatch.setattr(sm, "OUTPUTS_DIR", outputs)
    transcripts = {
        transcript_key: {
            "slug": slug,
            "runs": ["run_001"],
            "source_basename": slug,
            "source_path": str(transcript),
        }
    }
    slug_to_key = {slug: transcript_key}
    if extra_entries:
        for key, entry in extra_entries.items():
            transcripts[key] = entry
            slug_to_key[entry["slug"]] = key
    index_file.write_text(
        json.dumps({"transcripts": transcripts, "slug_to_key": slug_to_key}),
        encoding="utf-8",
    )
    return index_file


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
                        "processed_at": "2020-01-01T00:00:00",
                        "status": "completed",
                        "output_dir_path": str(outputs / "old_name"),
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


def test_rename_e2e_dry_run_leaves_filesystem_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_old_name_transcript_env(tmp_path, monkeypatch)
    transcript = env["transcript"]
    _register_slug_index(monkeypatch, env["outputs"], transcript)

    from transcriptx.web.services.rename_service import RenameService

    result = RenameService.rename(
        transcript_path=transcript, new_base_name="dry_target", dry_run=True
    )
    assert result.ok is True
    assert result.status == "dry_run"
    assert transcript.exists()
    assert not (transcript.parent / "dry_target.json").exists()
    assert (env["outputs"] / "old_name").exists()


def test_rename_e2e_repair_after_finalize_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_old_name_transcript_env(tmp_path, monkeypatch)
    transcript = env["transcript"]
    outputs = env["outputs"]
    _register_slug_index(monkeypatch, outputs, transcript)

    calls = {"n": 0}

    def flaky_finalize(old_dir, new_dir):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("simulated finalize failure")
        from transcriptx.core.utils.rename import finalize as fin

        return fin.finalize_output_directory_move(old_dir, new_dir)

    monkeypatch.setattr(
        "transcriptx.core.utils.rename.pipeline.finalize_output_directory_move",
        flaky_finalize,
    )

    from transcriptx.core.utils.rename.pipeline import (
        rename_managed_transcript,
        repair_managed_rename,
    )
    from transcriptx.core.utils.rename.outcome import RenameStatus

    outcome = rename_managed_transcript(transcript, "repaired_name")
    assert outcome.status == RenameStatus.committed_partial
    assert outcome.transaction_committed is True
    assert outcome.operation_id

    new_transcript = transcript.parent / "repaired_name.json"
    assert new_transcript.exists()
    assert not transcript.exists()

    repaired = repair_managed_rename(outcome.operation_id)
    assert repaired.transaction_committed is True
    assert repaired.status == RenameStatus.committed_complete
    assert (outputs / "repaired_name").exists()
    assert calls["n"] >= 2


def test_rename_e2e_slug_conflict_surfaces_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_old_name_transcript_env(tmp_path, monkeypatch)
    transcript = env["transcript"]
    outputs = env["outputs"]
    other = transcript.parent / "taken.json"
    other.write_text("{}")

    _register_slug_index(
        monkeypatch,
        outputs,
        transcript,
        extra_entries={
            "sha256:other": {
                "slug": "conflict_target",
                "runs": [],
                "source_basename": "conflict_target",
                "source_path": str(other),
            }
        },
    )

    from transcriptx.core.utils.rename.pipeline import rename_managed_transcript
    from transcriptx.core.utils.rename.outcome import RenameStatus

    outcome = rename_managed_transcript(transcript, "conflict_target")
    # Transcript rename may still commit; slug conflict → partial
    assert outcome.transaction_committed is True
    assert outcome.status == RenameStatus.committed_partial
    assert any(e.code == "slug_conflict" for e in outcome.errors)
