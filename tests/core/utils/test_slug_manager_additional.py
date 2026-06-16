from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.utils import slug_manager


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.unit
def test_load_index_returns_empty_on_parse_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    idx = tmp_path / ".transcriptx_index.json"
    idx.write_text("{bad", encoding="utf-8")
    monkeypatch.setattr(slug_manager, "INDEX_FILE", idx)
    assert slug_manager.load_index() == {"transcripts": {}, "slug_to_key": {}}


@pytest.mark.unit
def test_find_available_slug_disambiguates_taken_slots() -> None:
    idx = {"slug_to_key": {"a": "k1", "a__2": "k2"}}
    assert slug_manager.find_available_slug("a", "k3", idx) == "a__3"


@pytest.mark.unit
def test_register_transcript_reuses_slug_for_same_source_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    idx = tmp_path / ".transcriptx_index.json"
    monkeypatch.setattr(slug_manager, "INDEX_FILE", idx)
    _write(
        idx,
        {
            "transcripts": {
                "oldkey": {
                    "slug": "meeting",
                    "runs": ["r1"],
                    "source_basename": "meeting",
                    "source_path": "/x/meeting.json",
                }
            },
            "slug_to_key": {"meeting": "oldkey"},
        },
    )

    slug = slug_manager.register_transcript(
        transcript_key="newkey",
        transcript_path="/x/meeting.json",
        run_id="r2",
        source_basename="meeting",
        source_path="/x/meeting.json",
    )

    assert slug == "meeting"
    data = json.loads(idx.read_text(encoding="utf-8"))
    assert "oldkey" not in data["transcripts"]
    assert data["slug_to_key"]["meeting"] == "newkey"


@pytest.mark.unit
def test_unregister_and_list_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    idx = tmp_path / ".transcriptx_index.json"
    monkeypatch.setattr(slug_manager, "INDEX_FILE", idx)
    _write(
        idx,
        {
            "transcripts": {
                "k1": {"slug": "test__a", "runs": []},
                "k2": {"slug": "prod", "runs": []},
            },
            "slug_to_key": {"test__a": "k1", "prod": "k2"},
        },
    )

    assert slug_manager.list_slugs_matching("test__") == ["test__a"]
    assert slug_manager.unregister_slug("test__a") is True
    assert slug_manager.unregister_slug("test__a") is False
    assert slug_manager.get_transcript_key_for_slug("prod") == "k2"
    assert slug_manager.get_slug_for_transcript("k2") == "prod"


@pytest.mark.unit
def test_list_all_transcripts_returns_normalized_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    idx = tmp_path / ".transcriptx_index.json"
    monkeypatch.setattr(slug_manager, "INDEX_FILE", idx)
    _write(
        idx,
        {
            "transcripts": {
                "k": {
                    "slug": "s",
                    "runs": ["r"],
                    "source_basename": "b",
                    "source_path": "/x/b.json",
                }
            },
            "slug_to_key": {"s": "k"},
        },
    )

    rows = slug_manager.list_all_transcripts()
    assert rows == [
        {
            "transcript_key": "k",
            "slug": "s",
            "runs": ["r"],
            "source_basename": "b",
            "source_path": "/x/b.json",
        }
    ]
