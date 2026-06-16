from __future__ import annotations

from transcriptx.app.controllers.profile_controller import ProfileController
from transcriptx.web.ui.settings import configuration_panel as panel


def test_profile_controller_activation_scope_contracts_for_all_targets() -> None:
    ctrl = ProfileController()
    for target_id in ctrl.list_supported_targets():
        assert ctrl.can_edit_activation_for_scope(target_id, "Project")
        assert ctrl.can_edit_activation_for_scope(target_id, "Run override")
        assert not ctrl.can_edit_activation_for_scope(target_id, "Draft override")


def test_profile_controller_activation_scope_rejects_unknown_scope_for_all_targets() -> (
    None
):
    ctrl = ProfileController()
    for target_id in ctrl.list_supported_targets():
        assert not ctrl.can_edit_activation_for_scope(target_id, "Workspace")


def test_profile_selector_does_not_mutate_draft_activation_in_draft_scope(
    monkeypatch,
) -> None:
    class _StubSt:
        selectbox_called = False

        @staticmethod
        def caption(_msg: str) -> None:
            return None

        @classmethod
        def selectbox(cls, *_args, **_kwargs):
            cls.selectbox_called = True
            return "default"

    monkeypatch.setattr(panel, "st", _StubSt())
    draft_dot = {"analysis.active_acts_profile": "default"}
    panel._render_active_profile_selectors(
        draft_dot=draft_dot,
        scope="Draft override",
        form_scope_key="draft_override",
    )
    assert draft_dot == {"analysis.active_acts_profile": "default"}
    assert _StubSt.selectbox_called is False
