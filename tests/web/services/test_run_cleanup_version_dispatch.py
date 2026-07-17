"""Phase B0: version-dispatched journal readers and staging derivation (no bump)."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.services.run_cleanup import journal
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    CLEANUP_RESULT_SCHEMA_VERSION,
    JOURNAL_SCHEMA_VERSION,
    CleanupMode,
    CleanupResult,
    CleanupStatus,
    CleanupTarget,
    CleanupTargetResult,
    EntryClassification,
    SubjectType,
    TargetStatus,
    result_as_dict,
    result_from_mapping,
)
from transcriptx.web.services.run_cleanup.staging_identity import (
    intended_staging_path,
    resolve_staging_path_for_recovery,
    staging_path_for_journal_schema,
)


def _target(tmp_path: Path) -> CleanupTarget:
    run = tmp_path / "outputs" / "slug" / "20200101_000000_00000001"
    run.mkdir(parents=True)
    (run / "f.txt").write_text("x", encoding="utf-8")
    st = run.lstat()
    return CleanupTarget(
        subject_type=SubjectType.transcript,
        subject_id="slug",
        run_id="20200101_000000_00000001",
        root_relative_path="slug/20200101_000000_00000001",
        canonical_path=str(run.resolve()),
        mtime_ns=st.st_mtime_ns,
        filesystem_dev=int(st.st_dev),
        filesystem_ino=int(st.st_ino),
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint="a" * 64,
        safety_status=EntryClassification.eligible,
    )


@pytest.mark.unit
def test_versions_phase_b1() -> None:
    assert CLEANUP_POLICY_VERSION == 7
    assert JOURNAL_SCHEMA_VERSION == 3
    assert CLEANUP_RESULT_SCHEMA_VERSION == 2


@pytest.mark.unit
def test_schema3_staging_path_matches_intended(tmp_path: Path) -> None:
    t = _target(tmp_path)
    a = intended_staging_path(tmp_path / "outputs", "1_abcdefabcdef", t)
    b = staging_path_for_journal_schema(3, tmp_path / "outputs", "1_abcdefabcdef", t)
    assert a == b


@pytest.mark.unit
def test_recovery_prefers_stored_staging_path(tmp_path: Path) -> None:
    t = _target(tmp_path)
    stored = tmp_path / "outputs" / ".cleanup_staging" / "1_abcdefabcdef" / "custom"
    resolved = resolve_staging_path_for_recovery(
        output_root=tmp_path / "outputs",
        operation_id="1_abcdefabcdef",
        target=t,
        journal_schema_version=3,
        stored_staging_path=str(stored),
    )
    assert resolved == stored
    derived = resolve_staging_path_for_recovery(
        output_root=tmp_path / "outputs",
        operation_id="1_abcdefabcdef",
        target=t,
        journal_schema_version=3,
        stored_staging_path=None,
    )
    assert derived == intended_staging_path(tmp_path / "outputs", "1_abcdefabcdef", t)


@pytest.mark.unit
def test_unsupported_staging_schema_raises(tmp_path: Path) -> None:
    t = _target(tmp_path)
    with pytest.raises(ValueError, match="unsupported journal schema"):
        staging_path_for_journal_schema(99, tmp_path / "outputs", "1_abcdefabcdef", t)


@pytest.mark.unit
def test_result_as_dict_includes_schema_version() -> None:
    result = CleanupResult(
        operation_id="1_abcdefabcdef",
        plan_id="p",
        mode=CleanupMode.DELETE_ALL,
        status=CleanupStatus.SUCCESS,
        targets=(
            CleanupTargetResult(
                subject_type=SubjectType.transcript,
                subject_id="s",
                run_id="r",
                root_relative_path="s/r",
                canonical_path="/abs/s/r",
                status=TargetStatus.PHYSICAL_DELETED,
                filesystem_dev=1,
                filesystem_ino=2,
                root_kind=SubjectType.transcript,
            ),
        ),
        warnings=(),
        errors=(),
        visible_removed_count=1,
        physically_deleted_count=1,
    )
    payload = result_as_dict(result)
    assert payload["cleanup_result_schema_version"] == 2
    assert "root_kind" not in payload["targets"][0]
    roundtrip = result_from_mapping(payload)
    assert roundtrip.targets[0].filesystem_dev == 1
    assert roundtrip.targets[0].filesystem_ino == 2
    assert roundtrip.targets[0].root_kind is None


@pytest.mark.unit
def test_result_from_mapping_legacy_missing_version_defaults_to_v1() -> None:
    payload = {
        "operation_id": "1_abcdefabcdef",
        "plan_id": "p",
        "mode": "DELETE_ALL",
        "status": "SUCCESS",
        "targets": [
            {
                "subject_type": "transcript",
                "subject_id": "s",
                "run_id": "r",
                "root_relative_path": "s/r",
                "canonical_path": "/abs/s/r",
                "status": "PHYSICAL_DELETED",
                "filesystem_dev": 9,
                "filesystem_ino": 8,
            }
        ],
        "warnings": [],
        "errors": [],
    }
    result = result_from_mapping(payload)
    assert result.targets[0].filesystem_dev == 9
    assert result.targets[0].filesystem_ino == 8


@pytest.mark.unit
def test_load_typed_incompatible_for_unknown_schema(tmp_path: Path) -> None:
    state = tmp_path / "state"
    ops = state / "cleanup" / "operations"
    ops.mkdir(parents=True)
    oid = "1_abcdefabcdef"
    (ops / f"{oid}.json").write_text(
        '{"journal_schema_version": 99, "cleanup_policy_version": 4,'
        f' "operation_id": "{oid}", "plan_id": "p", "mode": "DELETE_ALL",'
        ' "policy_version": 4, "created_at": 1, "roots": [], "targets": [],'
        ' "status": "journaled"}\n',
        encoding="utf-8",
    )
    loaded = journal.load_operation_typed(
        state,
        oid,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    assert loaded.kind is journal.JournalLoadKind.INCOMPATIBLE


@pytest.mark.unit
def test_load_typed_decodes_schema3_when_expected_none(tmp_path: Path) -> None:
    from transcriptx.web.services.run_cleanup.models import CleanupPlan, RootIdentity

    state = tmp_path / "state"
    out = tmp_path / "outputs"
    out.mkdir()
    t = _target(tmp_path)
    root = RootIdentity(
        kind=SubjectType.transcript,
        configured_path=str(out),
        canonical_path=str(out.resolve()),
        dev=int(out.lstat().st_dev),
        ino=int(out.lstat().st_ino),
        is_symlink=False,
        exists=True,
    )
    plan = CleanupPlan(
        plan_id="p",
        mode=CleanupMode.DELETE_ALL,
        policy_version=CLEANUP_POLICY_VERSION,
        created_at_iso="2020-01-01T00:00:00+00:00",
        roots=(root,),
        candidates=(t,),
        retained=(),
        exclusions=(),
        warnings=(),
        blocking_errors=(),
        can_execute=True,
    )
    oid = "1_abcdefabcdef"
    journal.write_operation(state, operation_id=oid, plan=plan)
    loaded = journal.load_operation_typed(state, oid)
    assert loaded.kind is journal.JournalLoadKind.RETRYABLE
    assert loaded.data is not None
    assert loaded.data["journal_schema_version"] == 3
