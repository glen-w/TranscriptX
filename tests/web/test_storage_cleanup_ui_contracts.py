"""UI contract tests for Settings storage cleanup confirmation gating."""

from __future__ import annotations

from transcriptx.web.services.run_cleanup.models import (
    CONFIRM_DELETE_ALL,
    CONFIRM_DELETE_OLD,
    CleanupAuthorization,
    CleanupMode,
    authorization_is_valid,
)


def test_authorization_requires_exact_untrimmed_phrases():
    plan_id = "abc"
    assert authorization_is_valid(
        CleanupAuthorization(True, CONFIRM_DELETE_ALL, CleanupMode.DELETE_ALL, plan_id),
        expected_mode=CleanupMode.DELETE_ALL,
        expected_plan_id=plan_id,
    )
    assert not authorization_is_valid(
        CleanupAuthorization(True, "DELETE ALL ", CleanupMode.DELETE_ALL, plan_id),
        expected_mode=CleanupMode.DELETE_ALL,
        expected_plan_id=plan_id,
    )
    assert not authorization_is_valid(
        CleanupAuthorization(True, "delete all", CleanupMode.DELETE_ALL, plan_id),
        expected_mode=CleanupMode.DELETE_ALL,
        expected_plan_id=plan_id,
    )
    assert not authorization_is_valid(
        CleanupAuthorization(
            False, CONFIRM_DELETE_ALL, CleanupMode.DELETE_ALL, plan_id
        ),
        expected_mode=CleanupMode.DELETE_ALL,
        expected_plan_id=plan_id,
    )
    assert authorization_is_valid(
        CleanupAuthorization(True, CONFIRM_DELETE_OLD, CleanupMode.DELETE_OLD, plan_id),
        expected_mode=CleanupMode.DELETE_OLD,
        expected_plan_id=plan_id,
    )
    assert not authorization_is_valid(
        CleanupAuthorization(True, CONFIRM_DELETE_ALL, CleanupMode.DELETE_OLD, plan_id),
        expected_mode=CleanupMode.DELETE_OLD,
        expected_plan_id=plan_id,
    )


def test_storage_panel_exports_render():
    from transcriptx.web.ui.settings.storage_panel import render_storage_panel

    assert callable(render_storage_panel)


def test_render_cleanup_result_surfaces_operation_id_and_errors():
    from transcriptx.web.services.run_cleanup.models import (
        CleanupMode,
        CleanupResult,
        CleanupStatus,
    )
    from transcriptx.web.ui.settings import storage_panel as sp

    calls: list[tuple] = []

    class _St:
        def success(self, msg):
            calls.append(("success", msg))

        def warning(self, msg):
            calls.append(("warning", msg))

        def error(self, msg):
            calls.append(("error", msg))

        def info(self, msg):
            calls.append(("info", msg))

        def expander(self, *_a, **_k):
            class _Exp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            return _Exp()

        def caption(self, msg):
            calls.append(("caption", msg))

        def text(self, msg):
            calls.append(("text", msg))

    sp.st = _St()  # type: ignore[assignment]
    result = CleanupResult(
        operation_id="9_abcdefabcdef",
        plan_id="p",
        mode=CleanupMode.DELETE_ALL,
        status=CleanupStatus.PARTIAL,
        targets=(),
        warnings=("warn-a",),
        errors=("reason-one",),
        visible_removed_count=1,
        physically_deleted_count=0,
    )
    sp._render_cleanup_result(result)
    warning_msgs = [m for kind, m in calls if kind == "warning"]
    assert warning_msgs
    assert "9_abcdefabcdef" in warning_msgs[0]
    assert "reason-one" in warning_msgs[0]


def test_pending_staging_section_invokes_retry(monkeypatch):
    from transcriptx.web.services.run_cleanup.models import (
        CleanupMode,
        CleanupResult,
        CleanupStatus,
    )
    from transcriptx.web.ui.settings import storage_panel as sp

    retried: list[str] = []

    class _Svc:
        def list_pending_staging(self):
            return [
                {
                    "operation_id": "1_abcdefabcdef",
                    "plan_id": "p",
                    "mode": "DELETE_ALL",
                    "operation_status": "PARTIAL",
                    "subject_type": "transcript",
                    "subject_id": "s",
                    "run_id": "r",
                    "state": "staged",
                    "staging_path": "/tmp/x",
                    "canonical_path": "/tmp/s/r",
                }
            ]

        def retry_interrupted_staging(self, operation_id):
            retried.append(operation_id)
            return CleanupResult(
                operation_id=operation_id,
                plan_id="p",
                mode=CleanupMode.DELETE_ALL,
                status=CleanupStatus.SUCCESS,
                targets=(),
                warnings=(),
                errors=(),
            )

    clicks = {"retry": True}

    class _St:
        session_state = {}

        def subheader(self, *_a, **_k):
            pass

        def caption(self, *_a, **_k):
            pass

        def expander(self, *_a, **_k):
            class _Exp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            return _Exp()

        def text(self, *_a, **_k):
            pass

        def button(self, label, key=None):
            return bool(clicks.get("retry")) and "Retry" in label

        def success(self, msg):
            pass

        def warning(self, *_a, **_k):
            pass

        def error(self, *_a, **_k):
            pass

        def info(self, *_a, **_k):
            pass

    monkeypatch.setattr(sp, "RunCleanupService", _Svc)
    monkeypatch.setattr(sp, "st", _St())
    monkeypatch.setattr(
        sp, "clear_session_selections_for_removed_runs", lambda *a, **k: None
    )
    sp._render_pending_staging_section()
    assert retried == ["1_abcdefabcdef"]


def test_render_cleanup_result_failed_before_mutation_includes_operation_id():
    from transcriptx.web.services.run_cleanup.models import (
        CleanupMode,
        CleanupResult,
        CleanupStatus,
    )
    from transcriptx.web.ui.settings import storage_panel as sp

    calls: list[tuple] = []

    class _St:
        def success(self, msg):
            calls.append(("success", msg))

        def warning(self, msg):
            calls.append(("warning", msg))

        def error(self, msg):
            calls.append(("error", msg))

        def info(self, msg):
            calls.append(("info", msg))

        def expander(self, *_a, **_k):
            class _Exp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            return _Exp()

        def caption(self, msg):
            calls.append(("caption", msg))

        def text(self, msg):
            calls.append(("text", msg))

    sp.st = _St()  # type: ignore[assignment]
    result = CleanupResult(
        operation_id="7_abcdefabcdef",
        plan_id="p",
        mode=CleanupMode.DELETE_ALL,
        status=CleanupStatus.FAILED_BEFORE_MUTATION,
        targets=(),
        warnings=(),
        errors=("journal create failed",),
    )
    sp._render_cleanup_result(result)
    error_msgs = [m for kind, m in calls if kind == "error"]
    assert error_msgs
    assert "7_abcdefabcdef" in error_msgs[0]
    assert "journal create failed" in error_msgs[0]


def test_pending_staging_retry_partial_surfaces_errors(monkeypatch):
    from transcriptx.web.services.run_cleanup.models import (
        CleanupMode,
        CleanupResult,
        CleanupStatus,
    )
    from transcriptx.web.ui.settings import storage_panel as sp

    rendered: list = []

    class _Svc:
        def list_pending_staging(self):
            return [
                {
                    "operation_id": "2_abcdefabcdef",
                    "plan_id": "p",
                    "mode": "DELETE_ALL",
                    "operation_status": "PARTIAL",
                    "subject_type": "transcript",
                    "subject_id": "s",
                    "run_id": "r",
                    "state": "physical_delete_verified",
                    "staging_path": "/tmp/x",
                    "canonical_path": "/tmp/s/r",
                }
            ]

        def retry_interrupted_staging(self, operation_id):
            return CleanupResult(
                operation_id=operation_id,
                plan_id="p",
                mode=CleanupMode.DELETE_ALL,
                status=CleanupStatus.PARTIAL,
                targets=(),
                warnings=("warn-remnant",),
                errors=("still staged remnant",),
                visible_removed_count=1,
                physically_deleted_count=0,
            )

    class _St:
        session_state = {}

        def subheader(self, *_a, **_k):
            pass

        def caption(self, *_a, **_k):
            pass

        def expander(self, *_a, **_k):
            class _Exp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            return _Exp()

        def text(self, *_a, **_k):
            pass

        def button(self, label, key=None):
            return "Retry" in label

        def success(self, msg):
            rendered.append(("success", msg))

        def warning(self, msg):
            rendered.append(("warning", msg))

        def error(self, msg):
            rendered.append(("error", msg))

        def info(self, *_a, **_k):
            pass

    monkeypatch.setattr(sp, "RunCleanupService", _Svc)
    monkeypatch.setattr(sp, "st", _St())
    monkeypatch.setattr(
        sp, "clear_session_selections_for_removed_runs", lambda *a, **k: None
    )
    sp._render_pending_staging_section()
    warnings = [m for kind, m in rendered if kind == "warning"]
    assert warnings
    assert "2_abcdefabcdef" in warnings[0]
    assert "still staged remnant" in warnings[0]


def test_pending_section_empty_caption(monkeypatch):
    from transcriptx.web.ui.settings import storage_panel as sp

    captions: list[str] = []

    class _Svc:
        def list_pending_staging(self):
            return []

    class _St:
        def subheader(self, *_a, **_k):
            pass

        def caption(self, msg):
            captions.append(msg)

    monkeypatch.setattr(sp, "RunCleanupService", _Svc)
    monkeypatch.setattr(sp, "st", _St())
    sp._render_pending_staging_section()
    assert any("No pending staging" in c for c in captions)
