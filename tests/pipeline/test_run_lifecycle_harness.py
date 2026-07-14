"""Tests for run lifecycle harness."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

from transcriptx.core.pipeline.contracts import (
    PersistenceOutcome,
    RunConfigSnapshot,
    RunIdentity,
    RunRequest,
    TranscriptIdentity,
    TranscriptSource,
)
from transcriptx.core.pipeline.run_orchestrator import RunOrchestrator


@dataclass
class _FakeConfig:
    class output:  # noqa: N801 - mirrors runtime config shape
        dynamic_charts = "off"


@dataclass
class _FakeResolution:
    config: _FakeConfig
    snapshot: RunConfigSnapshot
    draft_override: dict | None


@contextmanager
def _noop_scope():
    yield


class RunLifecycleHarness:
    """Inject failures at lifecycle points and assert final statuses."""

    def __init__(self, orchestrator: RunOrchestrator):
        self.orchestrator = orchestrator

    def configure_happy_path(self) -> None:
        class _Ctx:
            def close(self):
                return None

        self.orchestrator.bootstrap.load_segments = lambda _p: [
            {"speaker": "A", "text": "x", "start": 0.0, "end": 1.0}
        ]
        self.orchestrator.bootstrap.compute_identity = (
            lambda _p, _s: TranscriptIdentity(
                transcript_identity_hash="tid",
                transcript_content_hash_full="tcontent",
                transcript_file_hash="tfile",
            )
        )
        self.orchestrator.bootstrap.validate_managed = lambda _p: None
        self.orchestrator.bootstrap.register = lambda **_k: RunIdentity(
            transcript_key="tid", run_id="rid", source_basename="base", slug="slug"
        )
        self.orchestrator.workspace.create = lambda **_k: type(
            "Workspace", (), {"output_dir": "/tmp/out"}
        )()
        self.orchestrator.workspace.scoped_transcript_output_dir = (
            lambda _tp, _od: _noop_scope()
        )
        self.orchestrator.configurator.resolve_and_apply = lambda _rd: _FakeResolution(
            config=_FakeConfig(),
            snapshot=RunConfigSnapshot(
                config_hash="cfg",
                config_source="default",
                draft_override_applied=False,
                schema_version=1,
            ),
            draft_override=None,
        )
        self.orchestrator.configurator.clear_draft_override = lambda **_k: None
        self.orchestrator.presenter.show_pre_run_review = lambda _r: None
        self.orchestrator.presenter.show_post_run_summary = lambda _s, _o, _r: None
        self.orchestrator.presenter.build_summary = lambda **_k: {"summary": "ok"}
        self.orchestrator._build_context = lambda **_k: (_Ctx(), 1)
        self.orchestrator.persistence.persist_run_outputs = (
            lambda **_k: PersistenceOutcome(
                name="canonical_results", success=True, severity="required"
            )
        )
        self.orchestrator.persistence.persist_processing_state = (
            lambda *_a, **_k: PersistenceOutcome(
                name="processing_state", success=True, severity="required"
            )
        )
        self.orchestrator.persistence.persist_run_report = lambda *_a, **_k: (
            PersistenceOutcome(name="run_report", success=True, severity="required")
        )
        self.orchestrator.persistence.persist_manifest = (
            lambda **_k: PersistenceOutcome(
                name="manifest", success=True, severity="required"
            )
        )

    def run(self) -> dict:
        request = RunRequest(
            transcript_source=TranscriptSource(kind="local_file", value="/tmp/t.json"),
            selected_modules=["sentiment"],
        )
        result = self.orchestrator.run(
            transcript_path="/tmp/t.json",
            request=request,
            speaker_options=None,
            on_event=None,
        )
        return {
            "status": result.status,
            "execution_status": result.execution_status,
            "final_status": result.final_status,
            "termination_reason": result.termination_reason,
        }


def test_lifecycle_harness_setup_failure_returns_failed(monkeypatch):
    orchestrator = RunOrchestrator()
    harness = RunLifecycleHarness(orchestrator)
    harness.configure_happy_path()
    orchestrator.bootstrap.load_segments = lambda _p: (_ for _ in ()).throw(
        ValueError("validation failure")
    )
    status = harness.run()
    assert status["status"] == "failed"
    assert status["execution_status"] == "failed"


def test_lifecycle_harness_optional_persistence_failure_downgrades_to_partial(
    monkeypatch,
):
    orchestrator = RunOrchestrator()
    harness = RunLifecycleHarness(orchestrator)
    harness.configure_happy_path()

    class _FakeDag:
        def get_execution_plan(self, _modules):
            return None

        def compute_review_before_run(self, **_k):
            return {}

        def execute_pipeline(self, **_k):
            return {
                "modules_run": ["sentiment"],
                "errors": [],
                "execution_order": ["sentiment"],
                "cache_hits": [],
                "module_results": {"sentiment": {"status": "success"}},
                "skipped_modules": [],
            }

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_orchestrator.create_dag_pipeline",
        lambda: _FakeDag(),
    )
    orchestrator.persistence.persist_manifest = lambda **_k: PersistenceOutcome(
        name="manifest", success=False, severity="optional"
    )
    status = harness.run()
    assert status["execution_status"] == "succeeded"
    assert status["final_status"] == "partial"
    assert status["status"] == "partial"


def test_lifecycle_harness_required_persistence_failure_forces_failed(monkeypatch):
    orchestrator = RunOrchestrator()
    harness = RunLifecycleHarness(orchestrator)
    harness.configure_happy_path()

    class _FakeDag:
        def get_execution_plan(self, _modules):
            return None

        def compute_review_before_run(self, **_k):
            return {}

        def execute_pipeline(self, **_k):
            return {
                "modules_run": ["sentiment"],
                "errors": [],
                "execution_order": ["sentiment"],
                "cache_hits": [],
                "module_results": {"sentiment": {"status": "success"}},
                "skipped_modules": [],
            }

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_orchestrator.create_dag_pipeline",
        lambda: _FakeDag(),
    )
    orchestrator.persistence.persist_run_report = lambda *_a, **_k: PersistenceOutcome(
        name="run_report", success=False, severity="required"
    )
    status = harness.run()
    assert status["execution_status"] == "succeeded"
    assert status["final_status"] == "failed"
    assert status["status"] == "failed"


def test_lifecycle_harness_keyboard_interrupt_marks_aborted(monkeypatch):
    orchestrator = RunOrchestrator()
    harness = RunLifecycleHarness(orchestrator)
    harness.configure_happy_path()

    class _FakeDag:
        def get_execution_plan(self, _modules):
            return None

        def compute_review_before_run(self, **_k):
            return {}

        def execute_pipeline(self, **_k):
            raise KeyboardInterrupt()

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_orchestrator.create_dag_pipeline",
        lambda: _FakeDag(),
    )
    status = harness.run()
    assert status["execution_status"] == "aborted"
    assert status["final_status"] == "aborted"
    assert status["status"] == "aborted"
    assert status["termination_reason"] == "cancellation"


def test_lifecycle_harness_setup_error_attempts_best_effort_terminal_event(monkeypatch):
    orchestrator = RunOrchestrator()
    harness = RunLifecycleHarness(orchestrator)
    harness.configure_happy_path()

    class _FakeDag:
        def get_execution_plan(self, _modules):
            return None

        def compute_review_before_run(self, **_k):
            return {}

        def execute_pipeline(self, **_k):
            raise RuntimeError("unreachable")

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_orchestrator.create_dag_pipeline",
        lambda: _FakeDag(),
    )
    orchestrator._build_context = lambda **_k: (_ for _ in ()).throw(
        RuntimeError("context build failed")
    )
    received: list[dict] = []
    request = RunRequest(
        transcript_source=TranscriptSource(kind="local_file", value="/tmp/t.json"),
        selected_modules=["sentiment"],
    )
    result = orchestrator.run(
        transcript_path="/tmp/t.json",
        request=request,
        speaker_options=None,
        on_event=lambda event: received.append(event),
    )
    assert result.execution_status == "failed"
    assert any(e.get("event") == "run_failed" for e in received)


def test_run_equivalence_real_vs_noop_event_wiring(monkeypatch):
    orchestrator = RunOrchestrator()
    harness = RunLifecycleHarness(orchestrator)
    harness.configure_happy_path()

    class _FakeDag:
        def get_execution_plan(self, _modules):
            return None

        def compute_review_before_run(self, **_k):
            return {}

        def execute_pipeline(self, **kwargs):
            cb = kwargs.get("on_event")
            if cb is not None:
                cb({"event": "run_started"})
                cb({"event": "run_completed"})
            return {
                "modules_run": ["sentiment"],
                "errors": [],
                "execution_order": ["sentiment"],
                "cache_hits": [],
                "module_results": {"sentiment": {"status": "success"}},
                "skipped_modules": [],
            }

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_orchestrator.create_dag_pipeline",
        lambda: _FakeDag(),
    )
    request = RunRequest(
        transcript_source=TranscriptSource(kind="local_file", value="/tmp/t.json"),
        selected_modules=["sentiment"],
    )
    real = orchestrator.run(
        transcript_path="/tmp/t.json",
        request=request,
        speaker_options=None,
        on_event=lambda _e: None,
    )
    noop = orchestrator.run(
        transcript_path="/tmp/t.json",
        request=request,
        speaker_options=None,
        on_event=None,
    )
    assert real.status == noop.status
    assert real.execution_status == noop.execution_status
    assert real.final_status == noop.final_status
    assert real.modules_run == noop.modules_run
    assert real.execution_order == noop.execution_order
    assert real.skipped_modules == noop.skipped_modules
    assert real.errors == noop.errors


def test_no_double_terminal_event_when_sink_and_persistence_fail(monkeypatch):
    orchestrator = RunOrchestrator()
    harness = RunLifecycleHarness(orchestrator)
    harness.configure_happy_path()

    class _FakeDag:
        def get_execution_plan(self, _modules):
            return None

        def compute_review_before_run(self, **_k):
            return {}

        def execute_pipeline(self, **kwargs):
            cb = kwargs.get("on_event")
            if cb is not None:
                cb({"event": "run_completed"})
            return {
                "modules_run": ["sentiment"],
                "errors": [],
                "execution_order": ["sentiment"],
                "cache_hits": [],
                "module_results": {"sentiment": {"status": "success"}},
                "skipped_modules": [],
            }

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_orchestrator.create_dag_pipeline",
        lambda: _FakeDag(),
    )

    def _raise_persistence(*_a, **_k):
        raise RuntimeError("persist exploded")

    orchestrator.persistence.persist_run_report = _raise_persistence
    received: list[dict] = []

    def flaky_sink(event):
        received.append(event)
        raise RuntimeError("sink exploded")

    request = RunRequest(
        transcript_source=TranscriptSource(kind="local_file", value="/tmp/t.json"),
        selected_modules=["sentiment"],
    )
    result = orchestrator.run(
        transcript_path="/tmp/t.json",
        request=request,
        speaker_options=None,
        on_event=flaky_sink,
    )
    terminal = [
        e for e in received if e.get("event") in {"run_failed", "run_completed"}
    ]
    assert len(terminal) <= 1
    assert result.final_status == "failed"
