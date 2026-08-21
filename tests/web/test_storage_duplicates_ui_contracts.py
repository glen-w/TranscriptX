"""UI contract tests for Settings duplicate-library cleanup confirmation."""

from __future__ import annotations

import inspect

from transcriptx.app.duplicate_cleanup.models import (
    CONFIRM_DELETE_DUPLICATES,
    DuplicateAuthorization,
    authorization_is_valid,
)
from transcriptx.web.ui.settings import storage_panel


def test_duplicate_authorization_requires_exact_untrimmed_phrase() -> None:
    plan_id = "abc"
    assert authorization_is_valid(
        DuplicateAuthorization(True, CONFIRM_DELETE_DUPLICATES, plan_id),
        expected_plan_id=plan_id,
    )
    assert not authorization_is_valid(
        DuplicateAuthorization(True, "DELETE DUPLICATES ", plan_id),
        expected_plan_id=plan_id,
    )
    assert not authorization_is_valid(
        DuplicateAuthorization(True, "delete duplicates", plan_id),
        expected_plan_id=plan_id,
    )
    assert not authorization_is_valid(
        DuplicateAuthorization(False, CONFIRM_DELETE_DUPLICATES, plan_id),
        expected_plan_id=plan_id,
    )
    assert not authorization_is_valid(
        DuplicateAuthorization(True, CONFIRM_DELETE_DUPLICATES, "other"),
        expected_plan_id=plan_id,
    )


def test_storage_panel_has_duplicate_section() -> None:
    assert callable(storage_panel.render_storage_panel)
    assert callable(storage_panel._render_duplicate_cleanup_section)
    source = inspect.getsource(storage_panel)
    assert "Duplicate library files" in source
    assert "CONFIRM_DELETE_DUPLICATES" in source
