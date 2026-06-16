from __future__ import annotations

from types import SimpleNamespace

import pytest

import transcriptx.core.pipeline.dag_pipeline_engine as engine


class _FakeLogger:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def info(self, message: str) -> None:
        self.infos.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)


class _FakeExecutor:
    def __init__(self, blocked: list[SimpleNamespace] | None = None) -> None:
        self._blocked = blocked or []
        self.reduce_calls: list[tuple[object, str, object]] = []

    def blocked_from_plan(self, _plan: object) -> list[SimpleNamespace]:
        return self._blocked

    def reduce_outcome(self, state: object, module: str, outcome: object) -> None:
        self.reduce_calls.append((state, module, outcome))


class _FakePipeline:
    class PipelineSetupError(RuntimeError):
        pass

    def __init__(self) -> None:
        self.logger = _FakeLogger()
        self._finalized = True
        self._executor = _FakeExecutor()
        self.phase_called = False
        self.context_seen = None
        self.finalize_called = False
        self.raise_on_finalize = False

    def _pipeline_emit(self, event_collector, on_event, event_dict) -> None:
        if event_collector is not None:
            event_collector.append(event_dict)
        if on_event is not None:
            on_event(event_dict)

    def _new_pipeline_results(
        self, transcript_path: str, selected_modules: list[str]
    ) -> dict:
        return {
            "transcript_path": transcript_path,
            "selected_modules": selected_modules,
            "errors": [],
            "modules_run": [],
            "skipped_modules": [],
            "cache_hits": [],
            "module_results": {},
            "status": "pending",
            "start_time": 0.0,
        }

    def _validate_pipeline_io(
        self, _transcript_path: str, _output_dir: str, _results: dict
    ) -> bool:
        return True

    def preflight_check(self, _selected_modules: list[str]) -> dict:
        return {"warnings": [], "all_importable": True, "missing_dependencies": []}

    def get_execution_plan(self, _selected_modules: list[str]) -> object:
        raise NotImplementedError

    def _new_executor_state(self, _results: dict) -> object:
        return object()

    def _run_sequential_execution_phase(self, **kwargs):
        self.phase_called = True
        self.context_seen = kwargs.get("context")
        return (False, 0, 0, 0, 0, None)

    def finalize(self) -> None:
        self.finalize_called = True
        if self.raise_on_finalize:
            raise ValueError("finalize failed")


def test_execute_pipeline_runtime_requires_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    monkeypatch.setattr(
        engine, "resolve_output_dir_for_run", lambda *_args, **_kwargs: "/tmp/out"
    )

    with pytest.raises(
        _FakePipeline.PipelineSetupError, match="PipelineContext must be injected"
    ):
        engine.execute_pipeline_runtime(
            pipeline,
            transcript_path="/tmp/transcript.json",
            selected_modules=["stats"],
            context=None,
        )


def test_execute_pipeline_runtime_plan_error_sets_setup_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    monkeypatch.setattr(
        engine, "resolve_output_dir_for_run", lambda *_args, **_kwargs: "/tmp/out"
    )

    finalize_calls: list[dict] = []

    def _fake_finalize_execution_results(**kwargs) -> None:
        finalize_calls.append(kwargs)

    monkeypatch.setattr(
        engine, "finalize_execution_results", _fake_finalize_execution_results
    )

    def _boom(_selected_modules: list[str]) -> object:
        raise ValueError("plan exploded")

    pipeline.get_execution_plan = _boom

    results = engine.execute_pipeline_runtime(
        pipeline,
        transcript_path="/tmp/transcript.json",
        selected_modules=["stats"],
        context=SimpleNamespace(),
    )

    assert results["status"] == "failed"
    assert "plan exploded" in results["errors"]
    assert finalize_calls, "expected setup-failure finalization call"
    assert finalize_calls[-1]["setup_failed"] is True
    assert finalize_calls[-1]["setup_error"] == "plan exploded"
    assert pipeline.phase_called is False


def test_execute_pipeline_runtime_setup_failure_emits_run_failed_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    monkeypatch.setattr(
        engine, "resolve_output_dir_for_run", lambda *_args, **_kwargs: "/tmp/out"
    )

    def _boom(_selected_modules: list[str]) -> object:
        raise ValueError("plan exploded")

    pipeline.get_execution_plan = _boom
    events: list[dict] = []

    results = engine.execute_pipeline_runtime(
        pipeline,
        transcript_path="/tmp/transcript.json",
        selected_modules=["stats"],
        context=SimpleNamespace(),
        event_collector=events,
    )

    failed_events = [event for event in events if event.get("event") == "run_failed"]
    assert results["status"] == "failed"
    assert len(failed_events) == 1
    assert failed_events[0]["message"] == "Pipeline failed during setup"
    assert failed_events[0]["error"] == "plan exploded"


def test_execute_pipeline_runtime_reduces_blocked_outcomes_and_runs_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    blocked = [SimpleNamespace(module="missing_dep", status="blocked")]
    pipeline._executor = _FakeExecutor(blocked=blocked)
    execution_plan = SimpleNamespace(deterministic_order=["stats"])

    monkeypatch.setattr(
        engine, "resolve_output_dir_for_run", lambda *_args, **_kwargs: "/tmp/out"
    )

    finalize_calls: list[dict] = []

    def _fake_finalize_execution_results(**kwargs) -> None:
        finalize_calls.append(kwargs)

    monkeypatch.setattr(
        engine, "finalize_execution_results", _fake_finalize_execution_results
    )
    pipeline.get_execution_plan = lambda _selected_modules: execution_plan

    results = engine.execute_pipeline_runtime(
        pipeline,
        transcript_path="/tmp/transcript.json",
        selected_modules=["stats"],
        context=SimpleNamespace(name="ctx"),
    )

    assert results["execution_order"] == ["stats"]
    assert len(pipeline._executor.reduce_calls) == 1
    state, module, outcome = pipeline._executor.reduce_calls[0]
    assert module == "missing_dep"
    assert outcome.status == "blocked"
    assert state is not None
    assert pipeline.phase_called is True
    assert pipeline.context_seen is not None
    assert finalize_calls, "expected finalization after sequential phase"
    assert finalize_calls[-1]["setup_failed"] is False


def test_execute_pipeline_runtime_uses_injected_plan_without_replanning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    injected_plan = SimpleNamespace(deterministic_order=["injected"])
    monkeypatch.setattr(
        engine, "resolve_output_dir_for_run", lambda *_args, **_kwargs: "/tmp/out"
    )
    monkeypatch.setattr(engine, "finalize_execution_results", lambda **_kwargs: None)

    def _unexpected_replan(_selected_modules: list[str]) -> object:
        raise AssertionError("get_execution_plan should not be called")

    pipeline.get_execution_plan = _unexpected_replan

    results = engine.execute_pipeline_runtime(
        pipeline,
        transcript_path="/tmp/transcript.json",
        selected_modules=["stats"],
        context=SimpleNamespace(),
        execution_plan=injected_plan,
    )

    assert results["execution_order"] == ["injected"]
    assert pipeline.phase_called is True


def test_execute_pipeline_runtime_event_collector_and_on_event_share_terminal_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    monkeypatch.setattr(
        engine, "resolve_output_dir_for_run", lambda *_args, **_kwargs: "/tmp/out"
    )
    pipeline.get_execution_plan = lambda _modules: SimpleNamespace(
        deterministic_order=[]
    )
    collected: list[dict] = []
    callback_events: list[dict] = []

    engine.execute_pipeline_runtime(
        pipeline,
        transcript_path="/tmp/transcript.json",
        selected_modules=["stats"],
        context=SimpleNamespace(),
        event_collector=collected,
        on_event=callback_events.append,
    )

    assert collected[-1]["event"] == "run_completed"
    assert callback_events[-1] == collected[-1]


def test_execute_pipeline_runtime_io_validation_failure_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    monkeypatch.setattr(
        engine, "resolve_output_dir_for_run", lambda *_args, **_kwargs: "/tmp/out"
    )
    pipeline._validate_pipeline_io = lambda *_args, **_kwargs: False
    pipeline._new_pipeline_results = lambda _path, _mods: {
        "errors": ["io invalid"],
        "modules_run": [],
        "status": "pending",
    }

    finalize_calls: list[dict] = []
    monkeypatch.setattr(
        engine,
        "finalize_execution_results",
        lambda **kwargs: finalize_calls.append(kwargs),
    )

    results = engine.execute_pipeline_runtime(
        pipeline,
        transcript_path="/tmp/transcript.json",
        selected_modules=["stats"],
        context=SimpleNamespace(),
    )
    assert results["errors"] == ["io invalid"]
    assert pipeline.phase_called is False
    assert finalize_calls[-1]["setup_failed"] is True
    assert finalize_calls[-1]["setup_error"] == "io invalid"


def test_execute_pipeline_runtime_preflight_logs_warnings_and_missing_imports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    monkeypatch.setattr(
        engine, "resolve_output_dir_for_run", lambda *_args, **_kwargs: "/tmp/out"
    )
    pipeline.preflight_check = lambda _modules: {
        "warnings": ["use caution"],
        "all_importable": False,
        "missing_dependencies": ["dep_a", "dep_b"],
    }
    pipeline.get_execution_plan = lambda _modules: SimpleNamespace(
        deterministic_order=["stats"]
    )

    monkeypatch.setattr(engine, "finalize_execution_results", lambda **_kwargs: None)
    engine.execute_pipeline_runtime(
        pipeline,
        transcript_path="/tmp/transcript.json",
        selected_modules=["stats"],
        context=SimpleNamespace(),
    )
    assert any("Preflight warning: use caution" in x for x in pipeline.logger.warnings)
    assert any("cannot be imported: dep_a, dep_b" in x for x in pipeline.logger.errors)


def test_execute_pipeline_runtime_has_no_internal_parallel_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    monkeypatch.setattr(
        engine, "resolve_output_dir_for_run", lambda *_args, **_kwargs: "/tmp/out"
    )
    pipeline.get_execution_plan = lambda _modules: SimpleNamespace(
        deterministic_order=["stats"]
    )
    monkeypatch.setattr(engine, "finalize_execution_results", lambda **_kwargs: None)

    engine.execute_pipeline_runtime(
        pipeline,
        transcript_path="/tmp/transcript.json",
        selected_modules=["stats"],
        context=SimpleNamespace(),
    )
    assert not any("parallel=True is ignored" in x for x in pipeline.logger.warnings)


def test_execute_pipeline_runtime_attempts_finalize_when_registry_not_finalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    pipeline._finalized = False
    monkeypatch.setattr(
        engine, "resolve_output_dir_for_run", lambda *_args, **_kwargs: "/tmp/out"
    )
    pipeline.get_execution_plan = lambda _modules: SimpleNamespace(
        deterministic_order=["stats"]
    )
    monkeypatch.setattr(engine, "finalize_execution_results", lambda **_kwargs: None)

    engine.execute_pipeline_runtime(
        pipeline,
        transcript_path="/tmp/transcript.json",
        selected_modules=["stats"],
        context=SimpleNamespace(),
    )
    assert pipeline.finalize_called is True


def test_execute_pipeline_runtime_finalize_error_is_logged_and_execution_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    pipeline._finalized = False
    pipeline.raise_on_finalize = True
    monkeypatch.setattr(
        engine, "resolve_output_dir_for_run", lambda *_args, **_kwargs: "/tmp/out"
    )
    pipeline.get_execution_plan = lambda _modules: SimpleNamespace(
        deterministic_order=["stats"]
    )
    monkeypatch.setattr(engine, "finalize_execution_results", lambda **_kwargs: None)

    engine.execute_pipeline_runtime(
        pipeline,
        transcript_path="/tmp/transcript.json",
        selected_modules=["stats"],
        context=SimpleNamespace(),
    )
    assert pipeline.phase_called is True
    assert any(
        "Registry finalization failed: finalize failed" in x
        for x in pipeline.logger.errors
    )
