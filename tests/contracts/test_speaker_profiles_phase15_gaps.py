"""Phase 1.5 gap-fill tests: dual series, supersede noop, recovery signal, UX AST."""

from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from transcriptx.core.speaker_profiles.aggregates import (
    AppearanceRow,
    OccurrenceMetrics,
    headline_eligible,
)
from transcriptx.core.speaker_profiles.errors import RepairRequiredError
from transcriptx.core.speaker_profiles.hashing import sha256_file
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.layout import link_path
from transcriptx.core.speaker_profiles.models import (
    OperationPlanActionV1,
    OperationPlanV1,
    SpeakerProfileOperationV1,
)
from transcriptx.core.speaker_profiles.operations import relative_link_path
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.store_io import (
    read_live_link,
    write_operation,
)
from transcriptx.core.speaker_profiles.time_series import build_time_series
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)
from transcriptx.web.page_modules import speakers as speakers_mod
from transcriptx.web.speaker_accent import (
    AccentResolveContext,
    resolve_speaker_accent,
    speaker_accent_color,
)
IMPORT_A = "550e8400-e29b-41d4-a716-446655440000"
IMPORT_B = "660e8400-e29b-41d4-a716-446655440001"


def _patch(monkeypatch: pytest.MonkeyPatch, transcripts: Path) -> None:
    metadata = transcripts / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR", transcripts
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.file_discovery.DIARISED_TRANSCRIPTS_DIR", transcripts
    )


def _managed(
    transcripts: Path,
    *,
    name: str,
    import_id: str,
    segments: list[dict[str, Any]] | None = None,
    imported_at: str = "2026-01-15T10:00:00+00:00",
) -> Path:
    originals = transcripts / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    archive_rel = f"originals/{name}.srt"
    (transcripts / archive_rel).write_text("x", encoding="utf-8")
    segs = segments or [
        {"speaker": "SPEAKER_00", "text": "Hello world", "start": 0.0, "end": 2.0},
        {"speaker": "SPEAKER_01", "text": "Hi there", "start": 2.0, "end": 4.0},
    ]
    doc = create_transcript_document(
        segs,
        SourceInfo(
            type="srt",
            original_path=archive_rel,
            imported_at=imported_at,
            file_hash="abc",
            file_mtime=0.0,
        ),
        TranscriptMetadata(
            duration_seconds=4.0, segment_count=len(segs), speaker_count=2
        ),
    )
    path = transcripts / f"{name}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    write_initial_sidecar(
        path,
        import_id=import_id,
        imported_at=imported_at,
        adapter_source_id="srt",
        source_upload_basename=f"{name}.srt",
        archived_original_relpath=archive_rel,
    )
    return path


def _svc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transcripts: Path) -> SpeakerProfileService:
    from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver

    _patch(monkeypatch, transcripts)
    profiles = tmp_path / "speaker_profiles"
    state = tmp_path / "state"
    profiles.mkdir(exist_ok=True)
    state.mkdir(exist_ok=True)
    resolver = ManagedTranscriptResolver(
        transcripts_dir=transcripts, discovery_root=transcripts
    )
    return SpeakerProfileService(root=profiles, state_dir=state, resolver=resolver)


def _row(
    *,
    link_id: str,
    managed_transcript_id: str,
    appearance_date: date | None,
    flag: str,
    words: int = 2,
    duration: float | None = 1.0,
    ignored: bool = False,
    local_speaker_key: str = "SPEAKER_00",
) -> AppearanceRow:
    return AppearanceRow(
        profile_id="p1",
        link_id=link_id,
        managed_transcript_id=managed_transcript_id,
        local_speaker_key=local_speaker_key,
        link_file_key="k",
        observed_transcript_relpath="a.json",
        current_relpath="a.json",
        appearance_date=appearance_date,
        flag=flag,  # type: ignore[arg-type]
        ignored=ignored,
        metrics=OccurrenceMetrics(
            words=words,
            turns=1,
            duration_seconds=duration,
            avg_turn_duration=duration,
            median_turn_duration=duration,
            wpm=None,
            timing_valid_turn_count=1 if duration is not None else 0,
        ),
        speaking_share=None,
        speaking_share_basis="unavailable",
    )


def test_mixed_eligibility_same_date_separate_series() -> None:
    day = date(2026, 1, 15)
    rows = (
        _row(link_id="ok", managed_transcript_id="a", appearance_date=day, flag="ok", words=10),
        _row(
            link_id="nr",
            managed_transcript_id="b",
            appearance_date=day,
            flag="needs_review",
            words=99,
        ),
    )
    dens = {"a": 10.0, "b": 10.0}
    headline = build_time_series(
        rows, metric="words", kind="headline", transcript_denominators=dens
    )
    all_series = build_time_series(
        rows, metric="words", kind="all", transcript_denominators=dens
    )
    assert len(headline.points) == 1
    assert headline.points[0].value == 10.0
    assert headline.points[0].source_appearance_ids == ("ok",)
    assert len(all_series.points) == 1
    assert all_series.points[0].value == 109.0
    assert set(all_series.points[0].source_appearance_ids) == {"ok", "nr"}
    assert headline_eligible(rows[0], include_ignored=False)
    assert not headline_eligible(rows[1], include_ignored=False)


def test_unknown_date_is_final_bucket() -> None:
    rows = (
        _row(
            link_id="u",
            managed_transcript_id="a",
            appearance_date=None,
            flag="ok",
            words=3,
        ),
        _row(
            link_id="d",
            managed_transcript_id="b",
            appearance_date=date(2026, 1, 10),
            flag="ok",
            words=5,
        ),
    )
    series = build_time_series(rows, metric="words", kind="all")
    assert [p.display_label for p in series.points] == ["2026-01-10", "Unknown date"]
    assert series.points[-1].display_label == "Unknown date"
    assert series.points[-1].value == 3.0


def test_zero_and_none_duration_share_buckets() -> None:
    day = date(2026, 1, 15)
    rows = (
        _row(
            link_id="z",
            managed_transcript_id="a",
            appearance_date=day,
            flag="ok",
            duration=0.0,
        ),
        _row(
            link_id="n",
            managed_transcript_id="b",
            appearance_date=day,
            flag="ok",
            duration=None,
        ),
    )
    dens = {"a": 5.0, "b": 5.0}
    series = build_time_series(
        rows, metric="speaking_share", kind="headline", transcript_denominators=dens
    )
    assert len(series.points) == 1
    # num = 0 + missing; denom unique a+b = 10 → 0.0
    assert series.points[0].value == 0.0

    empty_denom = build_time_series(
        rows, metric="speaking_share", kind="headline", transcript_denominators={}
    )
    assert empty_denom.points[0].value is None


def test_supersede_already_current_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(transcripts, name="a", import_id=IMPORT_A)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    key = link_file_key(IMPORT_A, "SPEAKER_00")
    link = read_live_link(key, root=svc.root)
    assert link is not None
    result = svc.supersede_link_fingerprint(
        operation_idempotency_key=str(uuid4()),
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
        expected_link_id=link.link_id,
        expected_fingerprint=link.occurrence_fingerprint,
    )
    assert result.noop is True
    assert created.profile_id == result.profile_id


def test_recover_operation_returns_cache_signal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(transcripts, name="a", import_id=IMPORT_A)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    # Craft a never-applied incomplete op intersecting the link path.
    key = link_file_key(IMPORT_A, "SPEAKER_00")
    rel = relative_link_path(key)
    op_id = str(uuid4())
    op = SpeakerProfileOperationV1(
        operation_id=op_id,
        operation_idempotency_key=str(uuid4()),
        op_type="unlink",
        phase="prepared",
        plan=OperationPlanV1(
            actions=[
                OperationPlanActionV1(
                    action="delete",
                    path=rel,
                    expected_before_sha256=sha256_file(link_path(key, root=svc.root)),
                    after_sha256=None,
                    staging_relpath=None,
                    backup_relpath=f"operations/{op_id}/backup/{rel}",
                )
            ]
        ),
        receipt={"profile_id": created.profile_id, "link_id": created.link_id},
    )
    write_operation(op, root=svc.root)
    result = svc.recover_operation(op_id)
    assert result.cache_signal.scopes
    assert "speaker_profiles" in result.cache_signal.scopes or "speaker_links" in result.cache_signal.scopes
    assert result.report.recovery_class in {
        "proven_aborted",
        "complete",
        "partial",
        "ambiguous",
        "needs_repair",
    }


def test_mutation_blocked_by_intersecting_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(transcripts, name="a", import_id=IMPORT_A)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    key = link_file_key(IMPORT_A, "SPEAKER_00")
    rel = relative_link_path(key)
    op_id = str(uuid4())
    write_operation(
        SpeakerProfileOperationV1(
            operation_id=op_id,
            operation_idempotency_key=str(uuid4()),
            op_type="unlink",
            phase="needs_repair",
            plan=OperationPlanV1(
                actions=[
                    OperationPlanActionV1(
                        action="delete",
                        path=rel,
                        expected_before_sha256="abc",
                        after_sha256=None,
                        staging_relpath=None,
                        backup_relpath=f"operations/{op_id}/backup/{rel}",
                    )
                ]
            ),
            receipt={},
        ),
        root=svc.root,
    )
    with pytest.raises(RepairRequiredError):
        svc.unlink(
            operation_idempotency_key=str(uuid4()),
            managed_transcript_id=IMPORT_A,
            local_speaker_key="SPEAKER_00",
            expected_link_id=created.link_id,
        )


def test_accent_resolve_precedence_linked_over_name_over_hash() -> None:
    hash_color = speaker_accent_color("Alice")
    ctx = AccentResolveContext(
        by_name={"alice": "#111111"},
        by_local_key={"SPEAKER_00": "#222222"},
    )
    assert (
        resolve_speaker_accent(
            "Alice", local_speaker_key="SPEAKER_00", context=ctx
        )
        == "#222222"
    )
    assert resolve_speaker_accent("Alice", context=ctx) == "#111111"
    assert resolve_speaker_accent("Alice") == hash_color
    assert resolve_speaker_accent("Alice", accent="#ABCDEF") == "#ABCDEF"


def test_payload_hash_idempotency_helper_stable_and_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, Any] = {}
    monkeypatch.setattr(speakers_mod.st, "session_state", state)
    digest_a = speakers_mod._payload_digest({"link_id": "x", "v": 1})
    digest_b = speakers_mod._payload_digest({"link_id": "x", "v": 1})
    digest_c = speakers_mod._payload_digest({"link_id": "x", "v": 2})
    assert digest_a == digest_b
    assert digest_a != digest_c
    assert len(digest_a) == 64
    a = speakers_mod._idempotency_key("unlink", {"link_id": "x", "v": 1})
    b = speakers_mod._idempotency_key("unlink", {"link_id": "x", "v": 1})
    c = speakers_mod._idempotency_key("unlink", {"link_id": "x", "v": 2})
    assert a == b
    assert a != c


def test_speakers_merged_readonly_and_fingerprint_gate_ast() -> None:
    path = Path(speakers_mod.__file__)
    src = path.read_text(encoding="utf-8")
    assert "_render_merged_readonly" in src
    assert "Open target profile" in src
    assert 'row.flag != "needs_review"' in src
    assert 'st.expander("Trends"' in src
    assert "build_profile_analytics_pack" in src
    assert "include_all_series" in src
    assert 'st.expander("Conversation partners"' in src
    assert "_render_merged_readonly(profile, profiles_by_id=profiles_by_id)" in src
    assert "_speakers_browser_fragment" in src
    assert "_rerun_ui" in src
    tree = ast.parse(src)
    found_early_return = False
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.FunctionDef)
            or node.name != "_speakers_browser_fragment"
        ):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.If):
                continue
            body = stmt.body
            for j, inner in enumerate(body):
                if (
                    isinstance(inner, ast.Expr)
                    and isinstance(inner.value, ast.Call)
                    and isinstance(inner.value.func, ast.Name)
                    and inner.value.func.id == "_render_merged_readonly"
                ):
                    if j + 1 < len(body) and isinstance(body[j + 1], ast.Return):
                        found_early_return = True
    assert found_early_return, "merged selection must return before detail/lifecycle"


def test_bundle_uses_memoized_occurrence_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from transcriptx.core.speaker_profiles.snapshot import build_aggregation_snapshot

    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(transcripts, name="a", import_id=IMPORT_A)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    snap = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    bundle = snap.bundles[IMPORT_A]
    assert created.profile_id in snap.appearances_by_profile
    occ = next(o for o in bundle.occurrences if o.local_speaker_key == "SPEAKER_00")
    assert occ.occurrence_fingerprint
    assert "SPEAKER_00" in bundle.metrics_by_key


def test_duplicate_transcript_denominator_counted_once() -> None:
    day = date(2026, 1, 15)
    # Distinct local keys on one transcript: sum numerators; denom once.
    rows = (
        _row(
            link_id="a0",
            managed_transcript_id="same",
            appearance_date=day,
            flag="ok",
            duration=2.0,
            words=5,
            local_speaker_key="SPEAKER_00",
        ),
        _row(
            link_id="a1",
            managed_transcript_id="same",
            appearance_date=day,
            flag="ok",
            duration=3.0,
            words=7,
            local_speaker_key="SPEAKER_01",
        ),
    )
    series = build_time_series(
        rows,
        metric="speaking_share",
        kind="headline",
        transcript_denominators={"same": 10.0},
    )
    assert len(series.points) == 1
    assert series.points[0].value == pytest.approx(0.5)  # (2+3)/10
    assert series.points[0].managed_transcript_ids == ("same",)

    # Same local key twice: keep one contribution (no double-count).
    dup_key = (
        _row(
            link_id="b0",
            managed_transcript_id="same",
            appearance_date=day,
            flag="ok",
            duration=2.0,
            local_speaker_key="SPEAKER_00",
        ),
        _row(
            link_id="b1",
            managed_transcript_id="same",
            appearance_date=day,
            flag="ok",
            duration=3.0,
            local_speaker_key="SPEAKER_00",
        ),
    )
    series2 = build_time_series(
        dup_key,
        metric="speaking_share",
        kind="headline",
        transcript_denominators={"same": 10.0},
    )
    assert series2.points[0].value == pytest.approx(0.2)  # smallest link_id keeps 2.0


def test_flag_precedence_full_chain() -> None:
    from transcriptx.core.speaker_profiles.aggregates import resolve_appearance_flag

    assert resolve_appearance_flag() == "ok"
    assert resolve_appearance_flag(ignored=True) == "ignored"
    assert resolve_appearance_flag(needs_review=True, ignored=True) == "needs_review"
    assert (
        resolve_appearance_flag(collision=True, needs_review=True, ignored=True)
        == "collision"
    )
    assert (
        resolve_appearance_flag(
            missing_source=True, collision=True, needs_review=True, ignored=True
        )
        == "missing_source"
    )
    assert (
        resolve_appearance_flag(
            repair_required=True,
            missing_source=True,
            collision=True,
            needs_review=True,
            ignored=True,
        )
        == "repair_required"
    )


def test_alias_normalize_and_clear_accent() -> None:
    from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
    from transcriptx.core.speaker_profiles.normalize import (
        apply_profile_update,
        normalize_aliases,
        normalize_profile_fields,
    )

    aliases = normalize_aliases(
        ["  Bob  ", "bob", "Alice", "", "Bobby", "BOB"],
        display_name="Alice",
    )
    assert aliases == ["Bob", "Bobby"]
    fields = normalize_profile_fields(
        display_name="  Alice  Smith ",
        aliases=["ali", "ALI", "Alice Smith"],
        accent_color="#abc",
    )
    assert fields.display_name == "Alice Smith"
    assert fields.aliases == ["ali"]
    assert fields.accent_color == "#AABBCC"

    profile = SpeakerProfileV1(
        profile_id="11111111-1111-4111-8111-111111111111",
        display_name="Alice",
        aliases=["A."],
        notes="n",
        accent_color="#112233",
        status="active",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    cleared = apply_profile_update(profile, clear_accent=True)
    assert cleared.accent_color is None
    with pytest.raises(Exception):
        apply_profile_update(profile, accent_color="#112233", clear_accent=True)


def test_corrupt_operation_surfaces_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from transcriptx.core.speaker_profiles.integrity import run_integrity_scan
    from transcriptx.core.speaker_profiles.layout import operations_dir
    from transcriptx.core.speaker_profiles.snapshot import build_aggregation_snapshot

    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(transcripts, name="a", import_id=IMPORT_A)
    svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    ops = operations_dir(svc.root)
    ops.mkdir(parents=True, exist_ok=True)
    corrupt = ops / f"{uuid4()}.op.json"
    corrupt.write_text("{not-json", encoding="utf-8")
    report = run_integrity_scan(svc.root)
    assert report.corrupt_operations
    assert not report.ok
    snap = build_aggregation_snapshot(root=svc.root, resolver=svc.resolver)
    assert snap.incomplete


def test_stale_supersede_fingerprint_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from transcriptx.core.speaker_profiles.errors import StaleConfirmationError

    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(transcripts, name="a", import_id=IMPORT_A)
    created = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    key = link_file_key(IMPORT_A, "SPEAKER_00")
    link = read_live_link(key, root=svc.root)
    assert link is not None
    with pytest.raises(StaleConfirmationError):
        svc.supersede_link_fingerprint(
            operation_idempotency_key=str(uuid4()),
            managed_transcript_id=IMPORT_A,
            local_speaker_key="SPEAKER_00",
            expected_link_id=link.link_id,
            expected_fingerprint="deadbeef" * 8,
        )
    assert created.link_id == link.link_id


def test_create_cache_signal_includes_managed_transcript_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    svc = _svc(tmp_path, monkeypatch, transcripts)
    _managed(transcripts, name="a", import_id=IMPORT_A)
    result = svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Alice",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    assert IMPORT_A in result.cache_signal.managed_transcript_ids
    assert result.profile_id in result.cache_signal.profile_ids
    assert result.link_id in result.cache_signal.link_ids
