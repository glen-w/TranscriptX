"""Tests for slug manager."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.utils import slug_manager


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_register_transcript_updates_slug_on_rename(tmp_path, monkeypatch) -> None:
    index_path = tmp_path / ".transcriptx_index.json"
    monkeypatch.setattr(slug_manager, "INDEX_FILE", index_path)

    transcript_key = "sha256:same-content"
    old_slug = "Supervision 9 may _ Transcription Export"
    new_slug = "260509_Ana_supervision_meeting"
    old_path = f"/mnt/transcripts/{old_slug}.json"
    new_path = f"/mnt/transcripts/{new_slug}.json"

    _write_json(
        index_path,
        {
            "transcripts": {
                transcript_key: {
                    "slug": old_slug,
                    "runs": ["20260323_140355_4dd7adbd"],
                    "source_basename": old_slug,
                    "source_path": old_path,
                }
            },
            "slug_to_key": {old_slug: transcript_key},
        },
    )

    returned_slug = slug_manager.register_transcript(
        transcript_key=transcript_key,
        transcript_path=new_path,
        run_id="20260323_143440_8513fa2c",
        source_basename=new_slug,
        source_path=new_path,
    )

    assert returned_slug == new_slug
    index = _read_json(index_path)
    assert index["transcripts"][transcript_key]["slug"] == new_slug
    assert index["transcripts"][transcript_key]["source_basename"] == new_slug
    assert index["transcripts"][transcript_key]["source_path"] == new_path
    assert "20260323_143440_8513fa2c" in index["transcripts"][transcript_key]["runs"]
    assert new_slug in index["slug_to_key"]
    assert old_slug not in index["slug_to_key"]


def test_register_transcript_keeps_old_slug_when_new_slug_taken(
    tmp_path, monkeypatch
) -> None:
    index_path = tmp_path / ".transcriptx_index.json"
    monkeypatch.setattr(slug_manager, "INDEX_FILE", index_path)

    current_key = "sha256:current"
    other_key = "sha256:other"
    old_slug = "old_name"
    desired_slug = "renamed_name"
    new_path = f"/mnt/transcripts/{desired_slug}.json"

    _write_json(
        index_path,
        {
            "transcripts": {
                current_key: {
                    "slug": old_slug,
                    "runs": ["r1"],
                    "source_basename": old_slug,
                    "source_path": f"/mnt/transcripts/{old_slug}.json",
                },
                other_key: {
                    "slug": desired_slug,
                    "runs": ["r2"],
                    "source_basename": desired_slug,
                    "source_path": new_path,
                },
            },
            "slug_to_key": {old_slug: current_key, desired_slug: other_key},
        },
    )

    returned_slug = slug_manager.register_transcript(
        transcript_key=current_key,
        transcript_path=new_path,
        run_id="r3",
        source_basename=desired_slug,
        source_path=new_path,
    )

    assert returned_slug == old_slug
    index = _read_json(index_path)
    assert index["transcripts"][current_key]["slug"] == old_slug
    assert index["slug_to_key"][old_slug] == current_key
    assert index["slug_to_key"][desired_slug] == other_key
