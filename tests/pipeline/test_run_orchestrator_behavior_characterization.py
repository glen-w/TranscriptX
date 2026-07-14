"""Tests for run orchestrator behavior characterization."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.domain.canonical_transcript import CanonicalTranscript
from transcriptx.core.pipeline.contracts import (
    ErrorKind,
    PersistenceOutcome,
    RunRequest,
    TranscriptIdentity,
    TranscriptSource,
)
from transcriptx.core.pipeline.dag_pipeline_errors import PipelineSetupError
from transcriptx.core.pipeline.run_orchestrator import RunOrchestrator, _combine_status
from transcriptx.core.pipeline.run_phase_dtos import (
    PreparedTranscript,
    PreparedWorkspace,
)


def _request() -> RunRequest:
    return RunRequest(
        transcript_source=TranscriptSource(kind="local_file", value="/tmp/t.json"),
        selected_modules=["stats"],
    )


def _prepared_transcript() -> PreparedTranscript:
    return PreparedTranscript(
        transcript_path="/tmp/t.json",
        canonical=CanonicalTranscript.from_segments([{"speaker": "A", "text": "hi"}]),
        transcript_identity=TranscriptIdentity(
            transcript_identity_hash="tx",
            transcript_content_hash_full="content",
            transcript_file_hash="file",
        ),
        transcript_key="tx",
        run_id="run",
        source_basename="t",
        slug="t",
    )


def _prepared_workspace() -> PreparedWorkspace:
    return PreparedWorkspace(
        output_dir="/tmp/out",
        config=SimpleNamespace(),
        config_snapshot=SimpleNamespace(
            config_hash="hash",
            config_source="default",
            draft_override_applied=False,
            schema_version=1,
        ),
        draft_override_used=False,
    )


@pytest.mark.parametrize(
    ("execution_status", "outcomes", "expected"),
    [
        ("succeeded", [], "succeeded"),
        ("succeeded", [PersistenceOutcome("x", False, "optional")], "partial"),
        ("succeeded", [PersistenceOutcome("x", False, "required")], "failed"),
        ("failed", [], "failed"),
        ("failed", [PersistenceOutcome("x", False, "optional")], "failed"),
        ("aborted", [], "aborted"),
        ("aborted", [PersistenceOutcome("x", False, "required")], "failed"),
    ],
)
def test_status_combination_matrix(execution_status, outcomes, expected) -> None:
    assert _combine_status(execution_status, outcomes) == expected


def test_keyboard_interrupt_marks_aborted_and_emits_terminal_event_once(
    monkeypatch,
) -> None:
    orchestrator = RunOrchestrator()
    monkeypatch.setattr(
        orchestrator,
        "_prepare_transcript",
        lambda *_args, **_kwargs: _prepared_transcript(),
    )
    monkeypatch.setattr(
        orchestrator,
        "_prepare_workspace",
        lambda *_args, **_kwargs: _prepared_workspace(),
    )
    monkeypatch.setattr(
        orchestrator,
        "_build_execution_plan",
        lambda *_args, **_kwargs: SimpleNamespace(
            plan=SimpleNamespace(),
            execution_plan_outcome=PersistenceOutcome(
                "execution_plan", True, "required"
            ),
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "_execute_plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr(
        orchestrator.persistence,
        "persist_run_outputs",
        lambda **_kwargs: PersistenceOutcome("canonical_results", True, "required"),
    )

    events: list[dict] = []
    result = orchestrator.run(
        transcript_path="/tmp/t.json",
        request=_request(),
        on_event=events.append,
    )

    assert result.execution_status == "aborted"
    assert result.termination_reason == "cancellation"
    assert [event["event"] for event in events].count("run_failed") == 1


def test_setup_error_emits_run_failed_terminal_event(monkeypatch) -> None:
    orchestrator = RunOrchestrator()
    monkeypatch.setattr(
        orchestrator,
        "_prepare_transcript",
        lambda *_args, **_kwargs: _prepared_transcript(),
    )
    monkeypatch.setattr(
        orchestrator,
        "_prepare_workspace",
        lambda *_args, **_kwargs: _prepared_workspace(),
    )
    monkeypatch.setattr(
        orchestrator,
        "_build_execution_plan",
        lambda *_args, **_kwargs: SimpleNamespace(
            plan=SimpleNamespace(),
            execution_plan_outcome=PersistenceOutcome(
                "execution_plan", True, "required"
            ),
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "_execute_plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            PipelineSetupError("context required")
        ),
    )
    monkeypatch.setattr(
        orchestrator.persistence,
        "persist_run_outputs",
        lambda **_kwargs: PersistenceOutcome("canonical_results", True, "required"),
    )

    events: list[dict] = []
    result = orchestrator.run(
        transcript_path="/tmp/t.json",
        request=_request(),
        on_event=events.append,
    )

    assert result.execution_status == "failed"
    assert "context required" in result.errors
    failed_events = [event for event in events if event.get("event") == "run_failed"]
    assert len(failed_events) == 1
    assert failed_events[0]["error"] == "context required"


def test_execute_plan_closes_context_when_engine_raises(monkeypatch) -> None:
    orchestrator = RunOrchestrator()
    context = SimpleNamespace(close=lambda: close_calls.append(True))
    close_calls: list[bool] = []

    class _FailingPipeline:
        def execute_pipeline(self, **_kwargs):
            raise RuntimeError("engine failed")

    planned = SimpleNamespace(
        dag_pipeline=_FailingPipeline(),
        plan=SimpleNamespace(),
        requirements_resolver=SimpleNamespace(),
        run_report=SimpleNamespace(),
    )
    monkeypatch.setattr(orchestrator, "_build_context", lambda **_kwargs: (context, 1))

    with pytest.raises(RuntimeError, match="engine failed"):
        orchestrator._execute_plan(
            planned,
            _prepared_transcript(),
            _prepared_workspace(),
            _request(),
            speaker_options=None,
            on_event=None,
        )

    assert close_calls == [True]


def test_system_exit_from_execution_is_not_swallowed(monkeypatch) -> None:
    orchestrator = RunOrchestrator()
    monkeypatch.setattr(
        orchestrator,
        "_prepare_transcript",
        lambda *_args, **_kwargs: _prepared_transcript(),
    )
    monkeypatch.setattr(
        orchestrator,
        "_prepare_workspace",
        lambda *_args, **_kwargs: _prepared_workspace(),
    )
    monkeypatch.setattr(
        orchestrator,
        "_build_execution_plan",
        lambda *_args, **_kwargs: SimpleNamespace(
            plan=SimpleNamespace(),
            execution_plan_outcome=PersistenceOutcome(
                "execution_plan", True, "required"
            ),
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "_execute_plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(SystemExit(3)),
    )

    with pytest.raises(SystemExit) as exc_info:
        orchestrator.run(transcript_path="/tmp/t.json", request=_request())

    assert exc_info.value.code == 3


def test_fallback_persistence_on_pre_persist_exception(monkeypatch) -> None:
    orchestrator = RunOrchestrator()
    persisted: list[dict] = []
    monkeypatch.setattr(
        orchestrator,
        "_prepare_transcript",
        lambda *_args, **_kwargs: _prepared_transcript(),
    )
    monkeypatch.setattr(
        orchestrator,
        "_prepare_workspace",
        lambda *_args, **_kwargs: _prepared_workspace(),
    )

    def _boom(*_args, **_kwargs):
        raise RuntimeError("before execution")

    monkeypatch.setattr(orchestrator, "_build_execution_plan", _boom)

    def _persist_run_outputs(**kwargs):
        persisted.append(kwargs)
        return PersistenceOutcome("canonical_results", True, "required")

    monkeypatch.setattr(
        orchestrator.persistence, "persist_run_outputs", _persist_run_outputs
    )

    result = orchestrator.run(transcript_path="/tmp/t.json", request=_request())

    assert result.execution_status == "failed"
    assert persisted
    assert persisted[0]["output_dir"] == "/tmp/out"
    assert persisted[0]["results"]["errors"]
    assert any(
        outcome.name == "run_result_envelope" for outcome in result.persistence_outcomes
    )


def test_run_result_invariants_on_failure(monkeypatch) -> None:
    orchestrator = RunOrchestrator()
    monkeypatch.setattr(
        orchestrator,
        "_prepare_transcript",
        lambda *_args, **_kwargs: _prepared_transcript(),
    )
    monkeypatch.setattr(
        orchestrator,
        "_prepare_workspace",
        lambda *_args, **_kwargs: _prepared_workspace(),
    )
    monkeypatch.setattr(
        orchestrator,
        "_build_execution_plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        orchestrator.persistence,
        "persist_run_outputs",
        lambda **_kwargs: PersistenceOutcome("canonical_results", True, "required"),
    )

    result = orchestrator.run(transcript_path="/tmp/t.json", request=_request())

    assert result.run_id == "run"
    assert result.transcript_key == "tx"
    assert isinstance(result.modules_run, list)
    assert isinstance(result.errors, list)
    assert isinstance(result.summary, dict)


def test_required_persistence_failure_sets_error_kind() -> None:
    outcome = PersistenceOutcome(
        name="canonical_results",
        success=False,
        severity="required",
        error_kind=ErrorKind.PERSISTENCE,
        error_message="disk full",
    )

    assert _combine_status("succeeded", [outcome]) == "failed"


def test_successful_execution_with_optional_persistence_failure_returns_partial(
    monkeypatch,
) -> None:
    orchestrator = RunOrchestrator()
    context = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(
        orchestrator,
        "_prepare_transcript",
        lambda *_args, **_kwargs: _prepared_transcript(),
    )
    monkeypatch.setattr(
        orchestrator,
        "_prepare_workspace",
        lambda *_args, **_kwargs: _prepared_workspace(),
    )
    monkeypatch.setattr(
        orchestrator,
        "_build_execution_plan",
        lambda *_args, **_kwargs: SimpleNamespace(
            plan=SimpleNamespace(),
            execution_plan_outcome=PersistenceOutcome(
                "execution_plan", True, "required"
            ),
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "_execute_plan",
        lambda *_args, **_kwargs: SimpleNamespace(
            dag_results={
                "errors": [],
                "modules_run": ["stats"],
                "execution_order": ["stats"],
                "cache_hits": [],
                "module_results": {},
                "skipped_modules": [],
            },
            context=context,
            execution_status="succeeded",
            summary={},
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "_persist_success_outcome",
        lambda *_args, **_kwargs: [
            PersistenceOutcome("optional_projection", False, "optional")
        ],
    )

    result = orchestrator.run(transcript_path="/tmp/t.json", request=_request())

    assert result.execution_status == "succeeded"
    assert result.final_status == "partial"
    assert result.status == "partial"
