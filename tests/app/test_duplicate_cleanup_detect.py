"""Duplicate library detection: bytes, canonical content, linked audio units."""

from __future__ import annotations

import json
from pathlib import Path

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
from transcriptx.app.duplicate_cleanup.detect import detect_duplicate_groups
from transcriptx.app.duplicate_cleanup.models import DuplicateKind, MemberRole
from transcriptx.app.duplicate_cleanup.scan import list_audio_files
from transcriptx.app.duplicate_cleanup.service import DuplicateCleanupService


def _fp(path: Path) -> InventoryFingerprint:
    return InventoryFingerprint(stamps=(FileStamp(str(path), 0, 0),))


def _row(
    path: Path,
    *,
    analysis: AnalysisState | None = None,
    speaker: SpeakerIdState | None = None,
    corrections: CorrectionsState | None = None,
) -> InventoryRow:
    return InventoryRow(
        transcript_path=path,
        transcript_key=None,
        slug=path.stem,
        title=path.stem,
        imported_at=None,
        duration_seconds=None,
        speaker_count=None,
        word_count=None,
        source_id=None,
        listing_integrity=FieldIntegrity.OK,
        speaker=speaker
        or SpeakerIdState(SpeakerIdStatus.NONE, FieldIntegrity.OK),
        corrections=corrections
        or CorrectionsState(CorrectionsStatus.NEVER_STARTED, FieldIntegrity.OK),
        analysis=analysis
        or AnalysisState(AnalysisStatus.UNANALYSED, FieldIntegrity.OK),
        last_activity_at=None,
        fingerprint=_fp(path),
    )


def _v1_doc(segments: list, *, note: str | None = None) -> dict:
    metadata: dict = {
        "duration_seconds": 2.0,
        "segment_count": len(segments),
        "speaker_count": 1,
        "word_count": 2,
    }
    if note is not None:
        metadata["note"] = note
    return {
        "schema_version": 1,
        "source": {
            "type": "manual",
            "original_path": "test.json",
            "imported_at": "2020-01-01T00:00:00+00:00",
        },
        "metadata": metadata,
        "segments": segments,
    }


_SEGMENTS_A = [
    {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
    {"speaker": "SPEAKER_01", "text": "World", "start": 1.0, "end": 2.0},
]
_SEGMENTS_B = [
    {"speaker": "SPEAKER_00", "text": "Other", "start": 0.0, "end": 1.0},
]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_size_bucket_skips_unique_audio(tmp_path: Path) -> None:
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    (recordings / "keep.mp3").write_bytes(b"unique-bytes-here")
    (recordings / "dup_a.mp3").write_bytes(b"xx")
    (recordings / "dup_b.mp3").write_bytes(b"xx")
    groups, _warnings = detect_duplicate_groups(
        audio_paths=list_audio_files(recordings, imports_dir=recordings / "imports"),
        transcript_paths=[],
    )
    assert len(groups) == 1
    names = {
        groups[0].keeper.fingerprint.path.name,
        *(extra.fingerprint.path.name for extra in groups[0].extras),
    }
    assert names == {"dup_a.mp3", "dup_b.mp3"}
    assert "keep.mp3" not in names


def test_list_audio_skips_imports(tmp_path: Path) -> None:
    recordings = tmp_path / "recordings"
    imports = recordings / "imports"
    imports.mkdir(parents=True)
    (recordings / "lib.mp3").write_bytes(b"aa")
    (imports / "staged.mp3").write_bytes(b"aa")
    found = list_audio_files(recordings, imports_dir=imports)
    assert [p.name for p in found] == ["lib.mp3"]


def test_transcript_byte_groups(tmp_path: Path) -> None:
    transcripts = tmp_path / "tx"
    a = transcripts / "a.json"
    b = transcripts / "b.json"
    payload = _v1_doc(_SEGMENTS_A)
    _write_json(a, payload)
    _write_json(b, payload)
    groups, _ = detect_duplicate_groups(audio_paths=[], transcript_paths=[a, b])
    assert len(groups) == 1
    assert groups[0].kind is DuplicateKind.TRANSCRIPT_BYTES


def test_content_hash_groups_across_filenames(tmp_path: Path) -> None:
    transcripts = tmp_path / "tx"
    a = transcripts / "meeting.json"
    b = transcripts / "meeting_copy.json"
    _write_json(a, _v1_doc(_SEGMENTS_A, note=None))
    _write_json(b, _v1_doc(_SEGMENTS_A, note="wrapper-diff"))
    assert a.read_bytes() != b.read_bytes()
    groups, _ = detect_duplicate_groups(audio_paths=[], transcript_paths=[a, b])
    assert len(groups) == 1
    assert groups[0].kind is DuplicateKind.TRANSCRIPT_CONTENT
    names = {
        groups[0].keeper.title,
        *(extra.title for extra in groups[0].extras),
    }
    assert names == {"meeting", "meeting_copy"}


def test_different_speakers_are_not_content_duplicates(tmp_path: Path) -> None:
    transcripts = tmp_path / "tx"
    a = transcripts / "one.json"
    b = transcripts / "two.json"
    other = [
        {"speaker": "Ada", "text": "Hello", "start": 0.0, "end": 1.0},
        {"speaker": "Bob", "text": "World", "start": 1.0, "end": 2.0},
    ]
    _write_json(a, _v1_doc(_SEGMENTS_A, note="a"))
    _write_json(b, _v1_doc(other, note="b"))
    groups, _ = detect_duplicate_groups(audio_paths=[], transcript_paths=[a, b])
    assert groups == []


def test_audio_linked_unique_transcript_warns(tmp_path: Path) -> None:
    recordings = tmp_path / "rec"
    recordings.mkdir()
    a_mp3 = recordings / "left.mp3"
    b_mp3 = recordings / "right.mp3"
    a_mp3.write_bytes(b"same-audio")
    b_mp3.write_bytes(b"same-audio")
    t_left = tmp_path / "left.json"
    t_right = tmp_path / "right.json"
    _write_json(t_left, _v1_doc(_SEGMENTS_A, note="left"))
    _write_json(t_right, _v1_doc(_SEGMENTS_B, note="right"))

    def find_linked(path: Path) -> list[Path]:
        if path.name == "left.mp3":
            return [t_left]
        if path.name == "right.mp3":
            return [t_right]
        return []

    groups, _ = detect_duplicate_groups(
        audio_paths=[a_mp3, b_mp3],
        transcript_paths=[t_left, t_right],
        find_linked=find_linked,
    )
    assert len(groups) == 1
    assert groups[0].kind is DuplicateKind.LINKED_UNIT
    assert groups[0].unique_transcript_at_risk is True
    assert any(extra.unique_transcript_at_risk for extra in groups[0].extras)


def test_keeper_prefers_analysed_copy(tmp_path: Path) -> None:
    transcripts = tmp_path / "tx"
    plain = transcripts / "plain.json"
    rich = transcripts / "rich.json"
    payload = _v1_doc(_SEGMENTS_A)
    _write_json(plain, payload)
    _write_json(rich, payload)
    rows = {
        str(rich.resolve()): _row(
            rich,
            analysis=AnalysisState(
                AnalysisStatus.COMPLETED,
                FieldIntegrity.OK,
                modules_succeeded=4,
                modules_eligible=4,
            ),
            speaker=SpeakerIdState(SpeakerIdStatus.COMPLETE, FieldIntegrity.OK),
            corrections=CorrectionsState(
                CorrectionsStatus.COMPLETE,
                FieldIntegrity.OK,
                accepted_count=3,
            ),
        ),
        str(plain.resolve()): _row(plain),
    }
    groups, _ = detect_duplicate_groups(
        audio_paths=[],
        transcript_paths=[plain, rich],
        rows=rows,
    )
    assert len(groups) == 1
    assert groups[0].keeper.fingerprint.path.name == "rich.json"
    assert groups[0].extras[0].fingerprint.path.name == "plain.json"


def test_preview_service_uses_injected_paths(tmp_path: Path) -> None:
    recordings = tmp_path / "rec"
    recordings.mkdir()
    a = recordings / "a.wav"
    b = recordings / "b.wav"
    a.write_bytes(b"zz")
    b.write_bytes(b"zz")
    preview = DuplicateCleanupService(
        audio_paths=[a, b],
        transcript_paths=[],
        inventory_rows=lambda _paths: {},
    ).preview()
    assert preview.can_execute
    assert preview.extra_count == 1
    assert preview.plan_id
    assert all(member.role is MemberRole.AUDIO for group in preview.groups for member in (group.keeper, *group.extras))
