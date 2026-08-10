"""Web contracts for Theme B transcript viewer corrections."""

from __future__ import annotations

from transcriptx.web.transcript_viewer.corrections_panel import (
    correction_widget_key,
)


def test_correction_widget_key_uses_identity_and_segment_id():
    k1 = correction_widget_key("abcd1234ffff", "seg-A", "w0")
    k2 = correction_widget_key("abcd1234ffff", "seg-B", "w0")
    k3 = correction_widget_key("ffff9999aaaa", "seg-A", "w0")
    assert "seg-A" in k1
    assert k1 != k2
    assert k1 != k3
    assert k1.startswith("tx_corr|")


def test_action_id_correct_in_viewer_registered():
    from transcriptx.web.action_menus.catalog import ACTIONS_BY_ID
    from transcriptx.web.action_menus.handlers import HANDLERS
    from transcriptx.web.action_menus.ids import ActionId

    assert ActionId.CORRECT_IN_VIEWER in ACTIONS_BY_ID
    assert ActionId.CORRECT_IN_VIEWER in HANDLERS
