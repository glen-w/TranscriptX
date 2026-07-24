"""Stage 0: speaker_profiles_v1 contract freezes (identity, fingerprints, models)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from transcriptx.core.speaker_profiles.dates import (
    appearance_date_from_sources,
    appearance_date_from_transcript_document,
)
from transcriptx.core.speaker_profiles.errors import (
    SpeakerKeyCollisionError,
    SpeakerProfileContractError,
    SpeakerProfilePathError,
)
from transcriptx.core.speaker_profiles.fingerprint import (
    canonicalize_fingerprint_timestamp,
    compute_occurrence_fingerprint,
)
from transcriptx.core.speaker_profiles.identity import (
    assert_no_speaker_key_collision,
    canonicalize_managed_transcript_id,
    link_file_key,
    local_speaker_key_from_raw,
)
from transcriptx.core.speaker_profiles.layout import (
    event_path,
    link_path,
    profile_path,
)
from transcriptx.core.speaker_profiles.models import (
    OperationPlanActionV1,
    SpeakerProfileEventV1,
    SpeakerProfileLinkV1,
    SpeakerProfileOperationV1,
    SpeakerProfileV1,
)
from transcriptx.core.speaker_profiles.path_safety import (
    assert_path_under_root,
    assert_speaker_profiles_root,
)
from transcriptx.core.speaker_profiles.signals import CacheInvalidationSignal
from transcriptx.core.speaker_profiles.versioning import (
    EVENT_SCHEMA_ID,
    LINK_SCHEMA_ID,
    OPERATION_SCHEMA_ID,
    PROFILE_SCHEMA_ID,
    SCHEMA_VERSION,
)


@pytest.mark.unit
def test_schema_ids_frozen() -> None:
    assert SCHEMA_VERSION == 1
    assert PROFILE_SCHEMA_ID == "transcriptx.speaker_profile.v1"
    assert LINK_SCHEMA_ID == "transcriptx.speaker_profile_link.v1"
    assert EVENT_SCHEMA_ID == "transcriptx.speaker_profile_event.v1"
    assert OPERATION_SCHEMA_ID == "transcriptx.speaker_profile_operation.v1"


@pytest.mark.unit
def test_managed_transcript_id_canonical_hyphenated_uuid() -> None:
    assert (
        canonicalize_managed_transcript_id("550e8400-e29b-41d4-a716-446655440000")
        == "550e8400-e29b-41d4-a716-446655440000"
    )
    assert (
        canonicalize_managed_transcript_id("550E8400E29B41D4A716446655440000")
        == "550e8400-e29b-41d4-a716-446655440000"
    )
    with pytest.raises(SpeakerProfileContractError):
        canonicalize_managed_transcript_id("not-a-uuid")
    with pytest.raises(SpeakerProfileContractError):
        canonicalize_managed_transcript_id("550e8400")  # truncated


@pytest.mark.unit
def test_link_file_key_canonical_json_sha256() -> None:
    mt = "550e8400-e29b-41d4-a716-446655440000"
    key = link_file_key(mt, "SPEAKER_00")
    payload = json.dumps(
        ["speaker_occurrence_key.v1", mt, "SPEAKER_00"],
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    assert key == hashlib.sha256(payload).hexdigest()
    assert key == link_file_key(mt.upper().replace("-", ""), "SPEAKER_00")


@pytest.mark.unit
def test_local_speaker_key_normalisation_and_collision() -> None:
    assert local_speaker_key_from_raw("speaker_0") == "SPEAKER_00"
    assert local_speaker_key_from_raw("0") == "SPEAKER_00"
    assert_no_speaker_key_collision(["SPEAKER_00", "SPEAKER_01"])
    with pytest.raises(SpeakerKeyCollisionError):
        assert_no_speaker_key_collision(["SPEAKER_00", "speaker_0", "0"])


@pytest.mark.unit
@pytest.mark.parametrize(
    "value,expected",
    [
        (1, "1.000000"),
        (1.0, "1.000000"),
        ("1.0", "1.000000"),
        ("1", "1.000000"),
        (1.23456789, "1.234568"),
        (float("nan"), None),
        (float("inf"), None),
        ("not-a-float", None),
        (None, None),
        (True, None),
    ],
)
def test_fingerprint_timestamp_canonicalisation(value: object, expected: str | None) -> None:
    assert canonicalize_fingerprint_timestamp(value) == expected


@pytest.mark.unit
def test_fingerprint_int_float_string_stable() -> None:
    segs_int = [{"start": 1, "end": 2, "text": "hi", "speaker": "SPEAKER_00"}]
    segs_float = [{"start": 1.0, "end": 2.0, "text": "hi", "speaker": "SPEAKER_00"}]
    segs_str = [{"start": "1.0", "end": "2.0", "text": "hi", "speaker": "SPEAKER_00"}]
    fp = compute_occurrence_fingerprint(segs_int)
    assert fp == compute_occurrence_fingerprint(segs_float)
    assert fp == compute_occurrence_fingerprint(segs_str)
    assert fp.startswith("occurrence_fingerprint.v1:")


@pytest.mark.unit
def test_fingerprint_excludes_timing_invalid_segment() -> None:
    with_invalid = [
        {"start": 1, "end": 2, "text": "a", "speaker": "S"},
        {"start": "bad", "end": 3, "text": "b", "speaker": "S"},
    ]
    only_valid = [{"start": 1, "end": 2, "text": "a", "speaker": "S"}]
    assert compute_occurrence_fingerprint(with_invalid) == compute_occurrence_fingerprint(
        only_valid
    )


@pytest.mark.unit
def test_profile_and_link_models_roundtrip() -> None:
    profile = SpeakerProfileV1(
        profile_id="11111111-1111-1111-1111-111111111111",
        display_name="Alice",
        aliases=["A."],
        notes=None,
        status="active",
        merged_into_profile_id=None,
        created_at="2026-07-23T12:00:00Z",
        updated_at="2026-07-23T12:00:00Z",
    )
    assert profile.schema_id == PROFILE_SCHEMA_ID
    link = SpeakerProfileLinkV1(
        link_id="22222222-2222-2222-2222-222222222222",
        managed_transcript_id="550e8400-e29b-41d4-a716-446655440000",
        observed_transcript_relpath="meeting.json",
        local_speaker_key="SPEAKER_00",
        profile_id=profile.profile_id,
        occurrence_fingerprint=compute_occurrence_fingerprint(
            [{"start": 0, "end": 1, "text": "x", "speaker": "SPEAKER_00"}]
        ),
        observed_label="Alice",
        created_at="2026-07-23T12:00:00Z",
        updated_at="2026-07-23T12:00:00Z",
    )
    assert link.status == "confirmed"
    with pytest.raises(ValidationError):
        SpeakerProfileLinkV1(
            link_id="22222222-2222-2222-2222-222222222222",
            managed_transcript_id="550E8400E29B41D4A716446655440000",  # not hyphenated form
            observed_transcript_relpath="meeting.json",
            local_speaker_key="SPEAKER_00",
            profile_id=profile.profile_id,
            occurrence_fingerprint="occurrence_fingerprint.v1:abc",
            created_at="2026-07-23T12:00:00Z",
            updated_at="2026-07-23T12:00:00Z",
        )


@pytest.mark.unit
def test_event_id_must_equal_idempotency_id() -> None:
    SpeakerProfileEventV1(
        event_id="33333333-3333-3333-3333-333333333333",
        idempotency_id="33333333-3333-3333-3333-333333333333",
        operation_idempotency_key="44444444-4444-4444-4444-444444444444",
        event_type="link_unlinked",
        created_at="2026-07-23T12:00:00Z",
    )
    with pytest.raises(ValidationError):
        SpeakerProfileEventV1(
            event_id="33333333-3333-3333-3333-333333333333",
            idempotency_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            operation_idempotency_key="44444444-4444-4444-4444-444444444444",
            event_type="link_unlinked",
            created_at="2026-07-23T12:00:00Z",
        )


@pytest.mark.unit
def test_operation_plan_write_and_delete_actions() -> None:
    write = OperationPlanActionV1(
        action="write",
        path="profiles/p.speaker_profile.json",
        expected_before_sha256=None,
        after_sha256="abc",
        staging_relpath="operations/op/staging/p.speaker_profile.json",
    )
    delete = OperationPlanActionV1(
        action="delete",
        path="links/k.speaker_link.json",
        expected_before_sha256="def",
        after_sha256=None,
        backup_relpath="operations/op/backup/k.speaker_link.json",
    )
    op = SpeakerProfileOperationV1(
        operation_id="55555555-5555-5555-5555-555555555555",
        operation_idempotency_key="66666666-6666-6666-6666-666666666666",
        op_type="create_profile_and_link",
        phase="prepared",
        plan={"actions": [write.model_dump(), delete.model_dump()]},
    )
    assert op.schema_id == OPERATION_SCHEMA_ID
    with pytest.raises(ValidationError):
        OperationPlanActionV1(
            action="write",
            path="profiles/p.speaker_profile.json",
            after_sha256=None,
            staging_relpath="operations/op/staging/x",
        )


@pytest.mark.unit
def test_appearance_date_precedence() -> None:
    assert appearance_date_from_sources(
        transcript_source_imported_at="2026-01-15T10:00:00Z",
        sidecar_imported_at="2025-01-01T00:00:00Z",
    ).isoformat() == "2026-01-15"
    assert appearance_date_from_sources(
        transcript_source_imported_at=None,
        sidecar_imported_at="2025-06-01T12:00:00+00:00",
    ).isoformat() == "2025-06-01"
    assert (
        appearance_date_from_sources(
            transcript_source_imported_at="not-a-date",
            sidecar_imported_at=None,
        )
        is None
    )
    doc = {"source": {"imported_at": "2026-03-01T00:00:00Z"}}
    assert appearance_date_from_transcript_document(doc).isoformat() == "2026-03-01"


@pytest.mark.unit
def test_symlink_root_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real_profiles"
    real.mkdir()
    link = tmp_path / "speaker_profiles"
    link.symlink_to(real)
    with pytest.raises(SpeakerProfilePathError):
        assert_speaker_profiles_root(link)


@pytest.mark.unit
def test_path_escape_rejected(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(SpeakerProfilePathError):
        assert_path_under_root(outside, root)


@pytest.mark.unit
def test_layout_paths_under_root(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    (root / "profiles").mkdir()
    (root / "links").mkdir()
    (root / "events").mkdir()
    pid = "11111111-1111-1111-1111-111111111111"
    key = "a" * 64
    eid = "33333333-3333-3333-3333-333333333333"
    assert profile_path(pid, root=root).parent == root / "profiles"
    assert link_path(key, root=root).parent == root / "links"
    assert event_path(eid, root=root).name == f"{eid}.speaker_event.json"


@pytest.mark.unit
def test_cache_invalidation_signal_requires_scope() -> None:
    signal = CacheInvalidationSignal(scopes=("speaker_profiles",), profile_ids=("p1",))
    assert signal.scopes == ("speaker_profiles",)
    with pytest.raises(ValueError):
        CacheInvalidationSignal(scopes=())


@pytest.mark.unit
def test_merged_profile_requires_target() -> None:
    with pytest.raises(ValidationError):
        SpeakerProfileV1(
            profile_id="11111111-1111-1111-1111-111111111111",
            display_name="Alice",
            status="merged",
            merged_into_profile_id=None,
            created_at="2026-07-23T12:00:00Z",
            updated_at="2026-07-23T12:00:00Z",
        )
