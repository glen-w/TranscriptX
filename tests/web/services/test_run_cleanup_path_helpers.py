"""Unit coverage for path_helpers, prune, and default protected paths."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.web.services.run_cleanup.deletion_phase import prune_subject_parent
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    CleanupMode,
    CleanupPlan,
    CleanupTarget,
    EntryClassification,
    RootIdentity,
    SubjectType,
)
from transcriptx.web.services.run_cleanup.path_helpers import (
    output_root_for_target,
    planned_root_for_target,
)
from transcriptx.web.services.run_cleanup.service import (
    RunCleanupService,
    default_protected_paths,
)
from transcriptx.web.services.run_cleanup.staging import StagingUnsafeError


def _target(
    *,
    subject_type: SubjectType,
    subject_id: str,
    run_id: str,
    canonical: str,
) -> CleanupTarget:
    return CleanupTarget(
        subject_type=subject_type,
        subject_id=subject_id,
        run_id=run_id,
        root_relative_path=f"{subject_id}/{run_id}",
        canonical_path=canonical,
        mtime_ns=1,
        filesystem_dev=1,
        filesystem_ino=1,
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint="a" * 64,
        safety_status=EntryClassification.eligible,
    )


def _plan(tmp_path: Path, *roots: RootIdentity, candidates=()) -> CleanupPlan:
    return CleanupPlan(
        plan_id="p",
        mode=CleanupMode.DELETE_ALL,
        policy_version=CLEANUP_POLICY_VERSION,
        created_at_iso="t",
        roots=roots,
        candidates=tuple(candidates),
        retained=(),
        exclusions=(),
        warnings=(),
        blocking_errors=(),
        can_execute=True,
    )


@pytest.mark.unit
def test_output_root_for_target_transcript_vs_group(tmp_path: Path) -> None:
    host = SimpleNamespace(
        outputs_dir=tmp_path / "outputs",
        group_outputs_dir=tmp_path / "groups",
    )
    t = _target(
        subject_type=SubjectType.transcript,
        subject_id="s",
        run_id="20200101_000000_00000001",
        canonical=str(tmp_path / "outputs" / "s" / "r"),
    )
    g = _target(
        subject_type=SubjectType.group,
        subject_id="g",
        run_id="20200101_000000_00000002",
        canonical=str(tmp_path / "groups" / "g" / "r"),
    )
    assert output_root_for_target(host, t) == host.outputs_dir
    assert output_root_for_target(host, g) == host.group_outputs_dir


@pytest.mark.unit
def test_planned_root_for_target_missing_raises(tmp_path: Path) -> None:
    out = tmp_path / "outputs"
    out.mkdir()
    root = RootIdentity(
        kind=SubjectType.transcript,
        configured_path=str(out),
        canonical_path=str(out.resolve()),
        dev=1,
        ino=1,
        is_symlink=False,
    )
    plan = _plan(tmp_path, root)
    group_target = _target(
        subject_type=SubjectType.group,
        subject_id="g",
        run_id="20200101_000000_00000001",
        canonical=str(tmp_path / "groups" / "g" / "r"),
    )
    with pytest.raises(StagingUnsafeError, match="no planned root"):
        planned_root_for_target(plan, group_target)


@pytest.mark.unit
def test_default_protected_paths_keys(tmp_path: Path) -> None:
    data = tmp_path / "data"
    state = tmp_path / "state"
    config = tmp_path / "config"
    paths = default_protected_paths(
        project_root=tmp_path, data_dir=data, state_dir=state, config_dir=config
    )
    assert set(paths) >= {
        "transcripts",
        "recordings",
        "corrections",
        "metadata",
        "groups_defs",
        "config",
        "state",
        "preprocessing",
        "wav_backup",
    }
    assert paths["transcripts"] == data / "transcripts"
    assert paths["state"] == state


@pytest.mark.unit
def test_prune_subject_parent_skips_output_root(tmp_path: Path) -> None:
    out = tmp_path / "outputs"
    groups = tmp_path / "groups"
    out.mkdir()
    groups.mkdir()
    run = out / "20200101_000000_00000001"
    run.mkdir()
    host = SimpleNamespace(outputs_dir=out, group_outputs_dir=groups)
    target = _target(
        subject_type=SubjectType.transcript,
        subject_id="ignored",
        run_id="20200101_000000_00000001",
        canonical=str(run),
    )
    # Parent is the outputs root itself — must not rmdir.
    assert prune_subject_parent(host, target) is None
    assert out.exists()


@pytest.mark.unit
def test_prune_subject_parent_removes_empty_subject(tmp_path: Path) -> None:
    out = tmp_path / "outputs"
    groups = tmp_path / "groups"
    out.mkdir()
    groups.mkdir()
    subject = out / "slug"
    run = subject / "20200101_000000_00000001"
    run.mkdir(parents=True)
    run.rmdir()  # leave empty subject parent
    host = SimpleNamespace(outputs_dir=out, group_outputs_dir=groups)
    target = _target(
        subject_type=SubjectType.transcript,
        subject_id="slug",
        run_id="20200101_000000_00000001",
        canonical=str(run),
    )
    assert prune_subject_parent(host, target) is None
    assert not subject.exists()


@pytest.mark.unit
def test_prune_subject_parent_nonempty_is_noop(tmp_path: Path) -> None:
    out = tmp_path / "outputs"
    groups = tmp_path / "groups"
    out.mkdir()
    groups.mkdir()
    subject = out / "slug"
    run = subject / "20200101_000000_00000001"
    run.mkdir(parents=True)
    (subject / "other.txt").write_text("keep", encoding="utf-8")
    host = SimpleNamespace(outputs_dir=out, group_outputs_dir=groups)
    target = _target(
        subject_type=SubjectType.transcript,
        subject_id="slug",
        run_id="20200101_000000_00000001",
        canonical=str(run),
    )
    assert prune_subject_parent(host, target) is None
    assert subject.exists()


@pytest.mark.unit
def test_prune_subject_parent_symlink_warns(tmp_path: Path) -> None:
    out = tmp_path / "outputs"
    groups = tmp_path / "groups"
    out.mkdir()
    groups.mkdir()
    real = tmp_path / "real_subject"
    real.mkdir()
    subject = out / "slug"
    subject.symlink_to(real)
    run = subject / "20200101_000000_00000001"
    # canonical path under symlink parent
    host = SimpleNamespace(outputs_dir=out, group_outputs_dir=groups)
    target = _target(
        subject_type=SubjectType.transcript,
        subject_id="slug",
        run_id="20200101_000000_00000001",
        canonical=str(run),
    )
    msg = prune_subject_parent(host, target)
    assert msg is not None
    assert "unsafe to prune" in msg


@pytest.mark.unit
def test_facade_list_pending_uses_journal_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Direct journal import must still honour module monkeypatches."""
    from transcriptx.web.services.run_cleanup import journal as journal_mod

    out = tmp_path / "outputs"
    out.mkdir()
    groups = out / "groups"
    groups.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    for name in ("transcripts", "recordings", "corrections", "groups"):
        (data / name).mkdir()
    (data / "transcripts" / "metadata").mkdir(parents=True)
    svc = RunCleanupService(
        outputs_dir=out,
        group_outputs_dir=groups,
        state_dir=state,
        project_root=tmp_path,
        data_dir=data,
        config_dir=tmp_path / "config",
    )
    monkeypatch.setattr(
        journal_mod, "list_pending_staging", lambda _state_dir: [{"patched": True}]
    )
    assert svc.list_pending_staging() == [{"patched": True}]
