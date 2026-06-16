from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import transcriptx.core.utils.paths as paths_mod
from transcriptx.core.utils import transcript_variant_paths as tvp
from transcriptx.io.speaker_map_inheritance import (
    apply_speaker_map_on_import,
    build_speaker_map_from_segments,
    try_inherit_speaker_map_from_base,
)
from transcriptx.io.speaker_map_resolver import SpeakerMapResolver
from transcriptx.services.speaker_studio.mapping_service import SpeakerMappingService


def _patch_transcript_library_paths(
    monkeypatch: pytest.MonkeyPatch, root: Path
) -> None:
    metadata_dir = root / "metadata"
    speaker_maps_dir = metadata_dir / "speaker_maps"
    originals_dir = root / "originals"
    for directory in (root, metadata_dir, speaker_maps_dir, originals_dir):
        directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        paths_mod,
        "PATHS",
        replace(
            paths_mod.PATHS,
            transcripts_dir=root,
            transcripts_metadata_dir=metadata_dir,
            transcripts_speaker_maps_dir=speaker_maps_dir,
            transcripts_originals_dir=originals_dir,
        ),
    )


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("meeting_fr", ("meeting", "fr")),
        ("team_meeting_fr", ("team_meeting", "fr")),
        ("meeting_en", ("meeting", "en")),
        ("meeting", None),
        ("meeting_auto", None),
        ("meeting_french", None),
        ("_fr", None),
    ],
)
def test_parse_flat_language_variant_stem(
    stem: str, expected: tuple[str, str] | None
) -> None:
    assert tvp.parse_flat_language_variant_stem(stem) == expected


def test_base_transcript_path_for_flat_variant(tmp_path: Path) -> None:
    variant = tmp_path / "meeting_fr.json"
    assert (
        tvp.base_transcript_path_for_flat_variant(variant) == tmp_path / "meeting.json"
    )
    assert tvp.base_transcript_path_for_flat_variant(tmp_path / "meeting.json") is None


def test_inherit_copies_map_ignored_and_db_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "transcripts"
    _patch_transcript_library_paths(monkeypatch, root)
    base = root / "meeting.json"
    variant = root / "meeting_fr.json"
    base.write_text('{"segments": []}', encoding="utf-8")
    variant.write_text('{"segments": []}', encoding="utf-8")

    SpeakerMappingService().bulk_update(
        str(base),
        speaker_map={"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"},
        ignored_speakers=["SPEAKER_02"],
        method="batch",
        speaker_id_to_db_id={"SPEAKER_00": 10, "SPEAKER_01": 11},
    )

    assert try_inherit_speaker_map_from_base(variant) is True
    state = SpeakerMapResolver().load_mapping(variant)
    assert state.speaker_map == {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
    assert state.ignored_speakers == ["SPEAKER_02"]
    assert state.speaker_id_to_db_id == {"SPEAKER_00": 10, "SPEAKER_01": 11}
    assert state.speaker_map_source == {
        "kind": "inherited_from_base",
        "base_transcript_relpath": "meeting.json",
    }


def test_inherit_skips_when_base_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "transcripts"
    _patch_transcript_library_paths(monkeypatch, root)
    variant = root / "meeting_fr.json"
    variant.write_text('{"segments": []}', encoding="utf-8")
    assert try_inherit_speaker_map_from_base(variant) is False


def test_inherit_skips_when_base_has_no_sidecar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "transcripts"
    _patch_transcript_library_paths(monkeypatch, root)
    base = root / "meeting.json"
    variant = root / "meeting_fr.json"
    base.write_text('{"segments": []}', encoding="utf-8")
    variant.write_text('{"segments": []}', encoding="utf-8")
    assert try_inherit_speaker_map_from_base(variant) is False


def test_inherit_succeeds_with_only_ignored_speakers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "transcripts"
    _patch_transcript_library_paths(monkeypatch, root)
    base = root / "meeting.json"
    variant = root / "meeting_fr.json"
    base.write_text('{"segments": []}', encoding="utf-8")
    variant.write_text('{"segments": []}', encoding="utf-8")
    SpeakerMappingService().bulk_update(
        str(base),
        speaker_map={},
        ignored_speakers=["SPEAKER_99"],
        method="batch",
    )
    assert try_inherit_speaker_map_from_base(variant) is True
    state = SpeakerMapResolver().load_mapping(variant)
    assert state.ignored_speakers == ["SPEAKER_99"]


def test_inherit_skips_when_variant_already_has_sidecar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "transcripts"
    _patch_transcript_library_paths(monkeypatch, root)
    base = root / "meeting.json"
    variant = root / "meeting_fr.json"
    base.write_text('{"segments": []}', encoding="utf-8")
    variant.write_text('{"segments": []}', encoding="utf-8")
    SpeakerMappingService().bulk_update(
        str(base),
        speaker_map={"SPEAKER_00": "Alice"},
        ignored_speakers=[],
        method="batch",
    )
    SpeakerMappingService().bulk_update(
        str(variant),
        speaker_map={"SPEAKER_00": "Existing"},
        ignored_speakers=[],
        method="batch",
    )
    assert try_inherit_speaker_map_from_base(variant) is False
    assert (
        SpeakerMapResolver().load_mapping(variant).speaker_map["SPEAKER_00"]
        == "Existing"
    )


def test_apply_speaker_map_on_import_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "transcripts"
    _patch_transcript_library_paths(monkeypatch, root)
    base = root / "meeting.json"
    variant = root / "meeting_fr.json"
    base.write_text('{"segments": []}', encoding="utf-8")
    variant.write_text('{"segments": []}', encoding="utf-8")
    SpeakerMappingService().bulk_update(
        str(base),
        speaker_map={"SPEAKER_00": "Alice"},
        ignored_speakers=[],
        method="batch",
    )

    apply_speaker_map_on_import(variant)
    first_sidecar = SpeakerMapResolver().load_mapping(variant)
    sidecar_path = paths_mod.speaker_map_path_for_transcript(variant)
    first_bytes = sidecar_path.read_bytes()

    apply_speaker_map_on_import(variant)
    second_sidecar = SpeakerMapResolver().load_mapping(variant)
    assert second_sidecar.speaker_map == first_sidecar.speaker_map
    assert sidecar_path.read_bytes() == first_bytes


def test_apply_speaker_map_on_import_does_not_call_segment_builder_when_inherited(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "transcripts"
    _patch_transcript_library_paths(monkeypatch, root)
    base = root / "meeting.json"
    variant = root / "meeting_fr.json"
    base.write_text('{"segments": []}', encoding="utf-8")
    variant.write_text('{"segments": []}', encoding="utf-8")
    SpeakerMappingService().bulk_update(
        str(base),
        speaker_map={"SPEAKER_00": "Alice"},
        ignored_speakers=[],
        method="batch",
    )

    called = {"count": 0}

    def _spy(*_args, **_kwargs):
        called["count"] += 1
        return {}

    monkeypatch.setattr(
        "transcriptx.io.speaker_map_inheritance.build_speaker_map_from_segments",
        _spy,
    )
    apply_speaker_map_on_import(variant)
    assert called["count"] == 0


def test_build_speaker_map_from_segments_uses_original_speaker() -> None:
    segments = [
        {
            "speaker": "SPEAKER_00",
            "text": "a",
            "original_cue": {"original_speaker": "Alice"},
        },
        {
            "speaker": "SPEAKER_00",
            "text": "b",
            "original_cue": {"original_speaker": "Alice"},
        },
        {
            "speaker": "SPEAKER_01",
            "text": "c",
            "original_cue": {"original_speaker": "Bob"},
        },
    ]
    assert build_speaker_map_from_segments(segments) == {
        "SPEAKER_00": "Alice",
        "SPEAKER_01": "Bob",
    }
