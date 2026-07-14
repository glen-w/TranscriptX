"""Tests for profile controller contracts."""

from __future__ import annotations

from transcriptx.app.controllers.profile_controller import ProfileController
from transcriptx.core.config import list_supported_profile_target_ids


def test_controller_rejects_unsupported_target() -> None:
    ctrl = ProfileController()
    assert ctrl.list_profiles("unsupported_target_xyz") == []
    assert ctrl.load_profile("unsupported_target_xyz", "x") == {}
    assert not ctrl.save_profile("unsupported_target_xyz", "x", {})
    assert not ctrl.create_profile("unsupported_target_xyz", "x", {})


def test_controller_default_mutation_restrictions(monkeypatch) -> None:
    class _PM:
        def save_profile(
            self, *_args, **_kwargs
        ):  # pragma: no cover - should not be called
            raise AssertionError("save should not be called for default")

        def import_profile(self, *_args, **_kwargs):  # pragma: no cover
            raise AssertionError("import should not be called for default")

        def export_profile(self, *_args, **_kwargs):  # pragma: no cover
            raise AssertionError("export should not be called for default")

        def rename_profile(self, *_args, **_kwargs):  # pragma: no cover
            raise AssertionError("rename should not be called for default")

        def delete_profile(self, *_args, **_kwargs):  # pragma: no cover
            raise AssertionError("delete should not be called for default")

    monkeypatch.setattr(
        "transcriptx.app.controllers.profile_controller.get_profile_manager",
        lambda: _PM(),
    )

    ctrl = ProfileController()
    assert ctrl.load_profile("acts", "default") == {}
    assert not ctrl.save_profile("acts", "default", {})
    assert not ctrl.import_profile("acts", "default", "/tmp/x.json")
    assert not ctrl.export_profile("acts", "default", "/tmp/x.json")
    assert not ctrl.rename_profile("acts", "default", "renamed")
    assert not ctrl.delete_profile("acts", "default")


def test_controller_scope_guard_for_activation() -> None:
    ctrl = ProfileController()
    assert ctrl.can_edit_activation_for_scope("acts", "Project")
    assert ctrl.can_edit_activation_for_scope("acts", "Run override")
    assert not ctrl.can_edit_activation_for_scope("acts", "Draft override")


def test_controller_scope_guard_rejects_unknown_scope() -> None:
    ctrl = ProfileController()
    assert not ctrl.can_edit_activation_for_scope("acts", "Workspace")


def test_controller_scope_guard_rejects_unknown_target() -> None:
    ctrl = ProfileController()
    assert not ctrl.can_edit_activation_for_scope("unknown_target", "Project")


def test_list_supported_targets_workflow_first() -> None:
    ctrl = ProfileController()
    targets = ctrl.list_supported_targets()
    assert targets[0] == "workflow"


def test_list_supported_targets_matches_canonical_contract_order() -> None:
    ctrl = ProfileController()
    assert ctrl.list_supported_targets() == list(list_supported_profile_target_ids())


def test_controller_proxies_profile_manager_for_supported_target(monkeypatch) -> None:
    calls = {"list_profiles": 0}

    class _PM:
        def list_profiles(self, target_id):
            calls["list_profiles"] += 1
            assert target_id == "acts"
            return ["default", "team"]

    monkeypatch.setattr(
        "transcriptx.app.controllers.profile_controller.get_profile_manager",
        lambda: _PM(),
    )

    ctrl = ProfileController()
    assert ctrl.list_profiles("acts") == ["default", "team"]
    assert calls["list_profiles"] == 1


def test_controller_injects_virtual_default_even_when_manager_empty(
    monkeypatch,
) -> None:
    class _PM:
        def list_profiles(self, _target_id):
            return []

    monkeypatch.setattr(
        "transcriptx.app.controllers.profile_controller.get_profile_manager",
        lambda: _PM(),
    )

    ctrl = ProfileController()
    assert ctrl.list_profiles("acts") == ["default"]


def test_controller_preserves_profile_manager_saved_profile_order(monkeypatch) -> None:
    class _PM:
        def list_profiles(self, _target_id):
            return ["recent", "older"]

    monkeypatch.setattr(
        "transcriptx.app.controllers.profile_controller.get_profile_manager",
        lambda: _PM(),
    )

    ctrl = ProfileController()
    assert ctrl.list_profiles("acts") == ["default", "recent", "older"]
