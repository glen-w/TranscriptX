"""CorrectionsStudioController delegates to CorrectionService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from transcriptx.services.corrections_studio.controller import (
    CorrectionsStudioController,
)


@patch("transcriptx.services.corrections_studio.controller.CorrectionService")
def test_controller_record_decision_delegates(mock_svc_cls: MagicMock) -> None:
    mock_svc = MagicMock()
    mock_svc_cls.return_value = mock_svc
    ctrl = CorrectionsStudioController()
    ctrl.record_decision("sid", "cid", "reject", selected_occurrence_keys=["k1"])
    mock_svc.record_decision.assert_called_once_with(
        "sid",
        "cid",
        "reject",
        selected_occurrence_keys=["k1"],
        learn_rule_params=None,
        review_target_raw=None,
    )


@patch("transcriptx.services.corrections_studio.controller.CorrectionService")
def test_controller_compute_preview_delegates(mock_svc_cls: MagicMock) -> None:
    mock_svc = MagicMock()
    mock_svc.compute_preview.return_value = {"preview": True}
    mock_svc_cls.return_value = mock_svc
    ctrl = CorrectionsStudioController()
    assert ctrl.compute_preview("sid") == {"preview": True}
    mock_svc.compute_preview.assert_called_once_with("sid")


@patch("transcriptx.services.corrections_studio.controller.CorrectionService")
def test_controller_apply_and_export_delegates(mock_svc_cls: MagicMock) -> None:
    mock_svc = MagicMock()
    mock_svc.apply_and_export.return_value = {"ok": True}
    mock_svc_cls.return_value = mock_svc
    ctrl = CorrectionsStudioController()
    assert ctrl.apply_and_export("sid", export_path="/out.json") == {"ok": True}
    mock_svc.apply_and_export.assert_called_once_with("sid", export_path="/out.json")
