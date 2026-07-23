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


def test_speakers_panel_renders_speaker_profile_toggles(monkeypatch):
    from transcriptx.web.speaker_profile_signals import (
        INCLUDE_IGNORED_SESSION_KEY,
        SHOW_ARCHIVED_SESSION_KEY,
        SHOW_MERGED_SESSION_KEY,
    )
    from transcriptx.web.ui.settings import speakers_panel as sp

    checkboxes: list[dict] = []
    subheaders: list[str] = []

    class _St:
        session_state = {}

        def subheader(self, title):
            subheaders.append(title)

        def checkbox(self, label, value=False, key=None, help=None):
            checkboxes.append(
                {"label": label, "value": value, "key": key, "help": help}
            )
            return value

        def caption(self, *_a, **_k):
            pass

        def success(self, *_a, **_k):
            pass

        def warning(self, *_a, **_k):
            pass

        def info(self, *_a, **_k):
            pass

        def error(self, *_a, **_k):
            pass

        def button(self, *_a, **_k):
            return False

        def number_input(self, *_a, **_k):
            return 40

    monkeypatch.setattr(sp, "st", _St())

    # Avoid voice-matching branch side effects.
    import transcriptx.core.speaker_profiles.voice.versioning as voice_ver

    monkeypatch.setattr(voice_ver, "FEATURE_GATE_COMPLETE", False)

    sp.render_speakers_panel()

    assert "Speaker profiles" in subheaders
    keys = {c["key"] for c in checkboxes}
    assert keys >= {
        INCLUDE_IGNORED_SESSION_KEY,
        SHOW_ARCHIVED_SESSION_KEY,
        SHOW_MERGED_SESSION_KEY,
    }


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


def test_execute_defers_result_and_avoids_widget_key_assignment(monkeypatch):
    """After execute, result is staged + rerun; widget keys are not assigned mid-run."""
    from transcriptx.web.services.run_cleanup.models import (
        CleanupMode,
        CleanupResult,
        CleanupStatus,
    )
    from transcriptx.web.ui.settings import storage_panel as sp

    session: dict = {
        sp._HANDLE_KEY: "h",
        sp._PLAN_ID_KEY: "plan",
        sp._MODE_KEY: CleanupMode.DELETE_OLD.value,
        sp._PREVIEW_KEY: type(
            "P",
            (),
            {
                "blocking_errors": (),
                "warnings": (),
                "transcript_subjects": 0,
                "group_subjects": 0,
                "run_count": 1,
                "file_count": 1,
                "size_estimate_bytes": 1,
                "candidates": (),
                "retained": (),
                "exclusions": (),
                "can_execute": True,
                "plan_id": "plan",
            },
        )(),
        sp._ACK_KEY: True,
        sp._PHRASE_KEY: CONFIRM_DELETE_OLD,
        sp._SESSION_ID_KEY: "sess",
    }
    calls: list[str] = []

    class _Svc:
        def execute_cleanup(self, *a, **k):
            return CleanupResult(
                operation_id="1_abcdefabcdef",
                plan_id="plan",
                mode=CleanupMode.DELETE_OLD,
                status=CleanupStatus.FAILED_BEFORE_MUTATION,
                targets=(),
                warnings=(),
                errors=("directory fsync failed",),
            )

    class _St:
        session_state = session

        def button(self, label, **k):
            return label == "Execute cleanup"

        def checkbox(self, *a, **k):
            return True

        def text_input(self, *a, **k):
            return CONFIRM_DELETE_OLD

        def rerun(self):
            calls.append("rerun")

        def radio(self, *a, **k):
            return "Delete old runs"

        def subheader(self, *a, **k):
            pass

        def caption(self, *a, **k):
            pass

        def warning(self, *a, **k):
            pass

        def info(self, *a, **k):
            pass

        def error(self, *a, **k):
            pass

        def success(self, *a, **k):
            pass

        def markdown(self, *a, **k):
            pass

        def columns(self, n):
            class _C:
                def metric(self, *a, **k):
                    pass

            return [_C() for _ in range(n)]

        def dataframe(self, *a, **k):
            pass

        def expander(self, *a, **k):
            class _E:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            return _E()

        def text(self, *a, **k):
            pass

        def metric(self, *a, **k):
            pass

    monkeypatch.setattr(sp, "RunCleanupService", _Svc)
    monkeypatch.setattr(sp, "st", _St())
    monkeypatch.setattr(
        sp, "clear_session_selections_for_removed_runs", lambda *a, **k: None
    )
    # Simulate post-widget execute path by calling the section; ack widgets
    # already "exist" via session keys — clear must not assign them.
    sp._render_cleanup_section()
    assert "rerun" in calls
    assert sp._RESULT_KEY in session
    assert session[sp._RESULT_KEY].status is CleanupStatus.FAILED_BEFORE_MUTATION
    assert sp._PREVIEW_KEY not in session
    # Widget keys must remain untouched on this run (pop happens next run).
    assert session.get(sp._ACK_KEY) is True


def test_pending_result_clears_ack_before_widgets(monkeypatch):
    from transcriptx.web.services.run_cleanup.models import (
        CleanupMode,
        CleanupResult,
        CleanupStatus,
    )
    from transcriptx.web.ui.settings import storage_panel as sp

    session: dict = {
        sp._RESULT_KEY: CleanupResult(
            operation_id="1_abcdefabcdef",
            plan_id="p",
            mode=CleanupMode.DELETE_OLD,
            status=CleanupStatus.SUCCESS,
            targets=(),
            warnings=(),
            errors=(),
            visible_removed_count=1,
            physically_deleted_count=1,
        ),
        sp._ACK_KEY: True,
        sp._PHRASE_KEY: "DELETE OLD RUNS",
    }
    errors: list[str] = []
    successes: list[str] = []

    class _St:
        session_state = session

        def button(self, *a, **k):
            return False

        def radio(self, *a, **k):
            return "Delete old runs"

        def subheader(self, *a, **k):
            pass

        def caption(self, *a, **k):
            pass

        def warning(self, *a, **k):
            pass

        def info(self, *a, **k):
            pass

        def error(self, msg):
            errors.append(msg)

        def success(self, msg):
            successes.append(msg)

        def expander(self, *a, **k):
            class _E:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            return _E()

        def text(self, *a, **k):
            pass

    monkeypatch.setattr(sp, "st", _St())
    sp._render_cleanup_section()
    assert successes
    assert sp._ACK_KEY not in session
    assert sp._PHRASE_KEY not in session
    assert sp._RESULT_KEY not in session


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
