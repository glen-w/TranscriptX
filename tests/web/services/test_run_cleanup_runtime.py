"""CleanupRuntime late-binding and façade shim wiring after Phase A extract."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.web.services.run_cleanup import journal as journal_mod
from transcriptx.web.services.run_cleanup import (
    CLEANUP_POLICY_VERSION,
    JOURNAL_SCHEMA_VERSION,
    CleanupMode,
    CleanupResult,
    CleanupStatus,
    RunCleanupService,
)
from transcriptx.web.services.run_cleanup import deletion_phase
from transcriptx.web.services.run_cleanup import finalization
from transcriptx.web.services.run_cleanup import journal_ops
from transcriptx.web.services.run_cleanup import results as results_mod


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
def test_phase_a_versions_match_package_exports() -> None:
    assert CLEANUP_POLICY_VERSION == 4
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
    # Same object identity as the runtime adapter (module late-binding).
    assert svc._runtime.journal is journal_mod


@pytest.mark.unit
class TestServiceShimDelegation:
    def test_persist_target_state_delegates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        svc = _svc(tmp_path)
        called = {}

        def fake(host, operation_id, **kwargs):
            called["host"] = host
            called["operation_id"] = operation_id
            called["kwargs"] = kwargs
            return "ok"

        monkeypatch.setattr(journal_ops, "persist_target_state", fake)
        assert (
            svc._persist_target_state(
                "1_abcdefabcdef",
                canonical_path="/x",
                state="staged",
                require_durable=True,
            )
            == "ok"
        )
        assert called["host"] is svc
        assert called["operation_id"] == "1_abcdefabcdef"
        assert called["kwargs"]["require_durable"] is True

    def test_status_from_journal_targets_delegates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            results_mod,
            "status_from_journal_targets",
            lambda targets: CleanupStatus.PARTIAL if targets else CleanupStatus.NOOP,
        )
        assert (
            RunCleanupService._status_from_journal_targets([{"state": "staged"}])
            is CleanupStatus.PARTIAL
        )
        assert RunCleanupService._status_from_journal_targets([]) is CleanupStatus.NOOP

    def test_physical_delete_one_delegates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        svc = _svc(tmp_path)
        called = {"n": 0}

        def fake(*_a, **_k):
            called["n"] += 1
            return SimpleNamespace(status="PHYSICAL_DELETED")

        monkeypatch.setattr(deletion_phase, "physical_delete_one", fake)
        svc._physical_delete_one("unused")
        assert called["n"] == 1

    def test_finalise_operation_delegates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        svc = _svc(tmp_path)
        sentinel = CleanupResult(
            operation_id="op",
            plan_id="p",
            mode=CleanupMode.DELETE_ALL,
            status=CleanupStatus.SUCCESS,
            targets=(),
            warnings=(),
            errors=(),
            visible_removed_count=0,
            physically_deleted_count=0,
        )
        monkeypatch.setattr(
            finalization, "finalise_operation", lambda *_a, **_k: sentinel
        )
        assert (
            svc._finalise_operation(
                handle_token="h",
                session_id="s",
                result=sentinel,
                operation_id="op",
                mutation_started=False,
            )
            is sentinel
        )

    def test_new_journaled_operation_delegates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        svc = _svc(tmp_path)
        monkeypatch.setattr(
            journal_ops, "new_journaled_operation", lambda *_a, **_k: "1_dddddddddddd"
        )
        assert svc._new_journaled_operation(SimpleNamespace(), []) == "1_dddddddddddd"
