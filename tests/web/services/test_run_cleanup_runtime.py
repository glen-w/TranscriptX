"""CleanupRuntime late-binding after Phase A extract / B-pre shim removal."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.services.run_cleanup import journal as journal_mod
from transcriptx.web.services.run_cleanup import (
    CLEANUP_POLICY_VERSION,
    JOURNAL_SCHEMA_VERSION,
    RunCleanupService,
)
from transcriptx.web.services.run_cleanup.path_helpers import validate_roots
from transcriptx.web.services.run_cleanup import results as results_mod
from transcriptx.web.services.run_cleanup.models import CleanupStatus


def _svc(tmp_path: Path, **kwargs) -> RunCleanupService:
    out = kwargs.pop("outputs_dir", tmp_path / "outputs")
    out.mkdir(parents=True, exist_ok=True)
    groups = kwargs.pop("group_outputs_dir", out / "groups")
    groups.mkdir(parents=True, exist_ok=True)
    state = kwargs.pop("state_dir", tmp_path / "state")
    state.mkdir(parents=True, exist_ok=True)
    data = kwargs.pop("data_dir", tmp_path / "data")
    data.mkdir(parents=True, exist_ok=True)
    for name in ("transcripts", "recordings", "corrections", "groups"):
        (data / name).mkdir(exist_ok=True)
    (data / "transcripts" / "metadata").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config").mkdir(exist_ok=True)
    return RunCleanupService(
        outputs_dir=out,
        group_outputs_dir=groups,
        state_dir=state,
        project_root=tmp_path,
        data_dir=data,
        config_dir=tmp_path / "config",
        **kwargs,
    )


@pytest.mark.unit
def test_phase_b_versions_match_package_exports() -> None:
    assert CLEANUP_POLICY_VERSION == 7
    assert JOURNAL_SCHEMA_VERSION == 3


@pytest.mark.unit
def test_runtime_journal_late_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Patches on the journal *module* must still apply via CleanupRuntime."""
    svc = _svc(tmp_path)
    sentinel = [{"operation_id": "patched", "state": "staged"}]
    monkeypatch.setattr(
        journal_mod, "list_pending_staging", lambda _state_dir: sentinel
    )
    assert svc.list_pending_staging() == sentinel
    assert svc._runtime.journal is journal_mod


@pytest.mark.unit
def test_facade_has_no_temporary_private_shims() -> None:
    assert not hasattr(RunCleanupService, "_validate_roots")
    assert not hasattr(RunCleanupService, "_physical_delete_one")
    assert not hasattr(RunCleanupService, "_status_from_journal_targets")


@pytest.mark.unit
def test_validate_roots_and_status_helpers_are_module_owned(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    roots, blocking = validate_roots(svc)
    assert blocking == []
    assert len(roots) == 2
    assert results_mod.status_from_journal_targets([]) is CleanupStatus.NOOP
