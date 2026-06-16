from __future__ import annotations

from types import SimpleNamespace

import pytest

import transcriptx.core.pipeline.dag_pipeline_execution as execution_module


class _FakeLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str) -> None:
        self.warnings.append(message)


class _FakePipeline:
    def __init__(self) -> None:
        self.nodes: dict[str, object] = {}
        self.logger = _FakeLogger()
        self.modules_run_seed: list[str] = []
        self.execute_calls: list[dict] = []
        self.reduce_calls: list[tuple[str, object]] = []
        self.side_effect_calls: list[tuple[str, object]] = []
        self.abort_on_fail = False
        self.missing_deps: dict[str, list[str]] = {}

    def _check_missing_dependencies(
        self, node: object, _modules_run: list[str]
    ) -> list[str]:
        return self.missing_deps.get(getattr(node, "name", ""), [])

    def _execute_single_module(self, **kwargs):
        self.execute_calls.append(kwargs)
        name = kwargs["module_name"]
        if name == "ok":
            return SimpleNamespace(
                status="success", duration_ms=12.0, skip_reason=None, error=None
            )
        if name == "skip":
            return SimpleNamespace(
                status="skipped", duration_ms=0.0, skip_reason="cache_hit", error=None
            )
        return SimpleNamespace(
            status="failed", duration_ms=1.0, skip_reason=None, error="boom"
        )

    def _reduce_module_outcome(
        self, *, module_name: str, outcome: object, results: dict
    ) -> None:
        self.reduce_calls.append((module_name, outcome))
        if outcome.status == "success":
            results["modules_run"].append(module_name)

    def _apply_module_side_effects(
        self,
        *,
        module_name: str,
        node: object,
        outcome: object,
        transcript_path: str,
        run_report: object,
    ) -> None:
        self.side_effect_calls.append((module_name, outcome))

    def _should_abort_pipeline(self, outcome: object, _results: dict) -> bool:
        return bool(self.abort_on_fail and outcome.status == "failed")


def _run(
    pipeline: _FakePipeline,
    *,
    execution_order: list[str],
    named_ref: list[int | None] | None = None,
    requirements_resolver: object | None = None,
):
    emitted: list[dict] = []
    results = {"modules_run": list(pipeline.modules_run_seed), "skipped_modules": []}
    named_speaker_count_ref = named_ref if named_ref is not None else [None]
    outcome = execution_module.run_sequential_execution_phase(
        pipeline,
        execution_order=execution_order,
        results=results,
        context=object(),
        transcript_path="/tmp/t.json",
        run_report=None,
        requirements_resolver=requirements_resolver,
        named_speaker_count_ref=named_speaker_count_ref,
        emit=lambda event: emitted.append(event),
    )
    return outcome, emitted, results, named_speaker_count_ref


def test_sequential_phase_empty_order_emits_run_started_and_returns_zeroes() -> None:
    pipeline = _FakePipeline()
    outcome, emitted, _, named_ref = _run(pipeline, execution_order=[])
    assert emitted and emitted[0]["event"] == "run_started"
    assert emitted[0]["total"] == 0
    assert outcome == (False, 0, 0, 0, 0, None)
    assert named_ref == [None]


def test_sequential_phase_unknown_module_logs_warning_and_continues() -> None:
    pipeline = _FakePipeline()
    outcome, emitted, results, _ = _run(pipeline, execution_order=["missing"])
    assert any("Unknown module: missing" in msg for msg in pipeline.logger.warnings)
    assert [e["event"] for e in emitted] == ["run_started"]
    assert results["modules_run"] == []
    assert outcome == (False, 1, 0, 0, 0, None)


def test_sequential_phase_missing_dependencies_marks_blocked_skip() -> None:
    pipeline = _FakePipeline()
    pipeline.nodes = {"needs": SimpleNamespace(name="needs")}
    pipeline.missing_deps = {"needs": ["dep_a"]}
    outcome, emitted, results, _ = _run(pipeline, execution_order=["needs"])
    assert emitted[-1]["event"] == "module_skipped"
    assert "missing_dependencies" in emitted[-1]["message"]
    assert results["skipped_modules"][0]["module"] == "needs"
    assert results["skipped_modules"][0]["execution_status"] == "blocked"
    assert "dep_a" in results["skipped_modules"][0]["reason"]
    assert outcome == (False, 1, 0, 1, 0, None)


def test_sequential_phase_missing_dependency_chain_includes_nested_requirements() -> (
    None
):
    pipeline = _FakePipeline()
    pipeline.nodes = {
        "needs": SimpleNamespace(name="needs"),
        "dep_a": SimpleNamespace(name="dep_a"),
    }
    pipeline.missing_deps = {
        "needs": ["dep_a"],
        "dep_a": ["base"],
    }

    outcome, _emitted, results, _ = _run(pipeline, execution_order=["needs"])

    assert outcome == (False, 1, 0, 1, 0, None)
    reason = results["skipped_modules"][0]["reason"]
    assert "needs: Missing dependencies ['dep_a']" in reason
    assert "dep_a (which requires ['base'])" in reason


def test_sequential_phase_fetches_named_speaker_count_once_and_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    pipeline.nodes = {
        "ok": SimpleNamespace(name="ok"),
        "ok2": SimpleNamespace(name="ok2"),
    }
    calls: list[str] = []

    def _fake_count(path: str) -> int:
        calls.append(path)
        return 3

    monkeypatch.setattr(execution_module, "named_speaker_count_for_path", _fake_count)
    _run(pipeline, execution_order=["ok", "ok2"])
    assert calls == ["/tmp/t.json"]
    assert all(call["named_speaker_count"] == 3 for call in pipeline.execute_calls)


def test_sequential_phase_named_speaker_count_failure_falls_back_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    pipeline.nodes = {"ok": SimpleNamespace(name="ok")}
    monkeypatch.setattr(
        execution_module,
        "named_speaker_count_for_path",
        lambda _path: (_ for _ in ()).throw(RuntimeError("count failed")),
    )
    _run(pipeline, execution_order=["ok"])
    assert pipeline.execute_calls[0]["named_speaker_count"] is None


def test_sequential_phase_success_updates_counters_and_side_effect_calls() -> None:
    pipeline = _FakePipeline()
    pipeline.nodes = {"ok": SimpleNamespace(name="ok")}
    outcome, emitted, results, _ = _run(pipeline, execution_order=["ok"])
    assert [e["event"] for e in emitted] == [
        "run_started",
        "module_started",
        "module_completed",
    ]
    assert results["modules_run"] == ["ok"]
    assert len(pipeline.reduce_calls) == 1
    assert len(pipeline.side_effect_calls) == 1
    assert outcome == (False, 1, 1, 0, 0, None)


def test_sequential_phase_skipped_outcome_emits_skip_reason() -> None:
    pipeline = _FakePipeline()
    pipeline.nodes = {"skip": SimpleNamespace(name="skip")}
    outcome, emitted, _, _ = _run(pipeline, execution_order=["skip"])
    assert emitted[-1]["event"] == "module_skipped"
    assert emitted[-1]["message"] == "cache_hit"
    assert outcome == (False, 1, 0, 1, 0, None)


def test_sequential_phase_failed_outcome_continues_when_not_fail_fast() -> None:
    pipeline = _FakePipeline()
    pipeline.nodes = {
        "fail": SimpleNamespace(name="fail"),
        "ok": SimpleNamespace(name="ok"),
    }
    outcome, emitted, _, _ = _run(pipeline, execution_order=["fail", "ok"])
    events = [e["event"] for e in emitted]
    assert events == [
        "run_started",
        "module_started",
        "module_failed",
        "module_started",
        "module_completed",
    ]
    assert outcome == (False, 2, 1, 0, 1, None)


def test_sequential_phase_failed_outcome_aborts_when_policy_requests_abort() -> None:
    pipeline = _FakePipeline()
    pipeline.abort_on_fail = True
    pipeline.nodes = {
        "fail": SimpleNamespace(name="fail"),
        "ok": SimpleNamespace(name="ok"),
    }
    outcome, emitted, _, _ = _run(pipeline, execution_order=["fail", "ok"])
    assert [e["event"] for e in emitted] == [
        "run_started",
        "module_started",
        "module_failed",
    ]
    assert outcome == (True, 2, 0, 0, 1, "boom")


def test_sequential_phase_uses_preseeded_named_speaker_count_without_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline()
    pipeline.nodes = {"ok": SimpleNamespace(name="ok")}
    lookups: list[str] = []

    def _fake_count(path: str) -> int:
        lookups.append(path)
        return 9

    monkeypatch.setattr(execution_module, "named_speaker_count_for_path", _fake_count)
    _run(pipeline, execution_order=["ok"], named_ref=[7])
    assert lookups == []
    assert pipeline.execute_calls[0]["named_speaker_count"] == 7


def test_sequential_phase_forwards_requirements_resolver_to_module_execution() -> None:
    pipeline = _FakePipeline()
    pipeline.nodes = {"ok": SimpleNamespace(name="ok")}
    resolver = object()

    _run(pipeline, execution_order=["ok"], requirements_resolver=resolver)

    assert pipeline.execute_calls[0]["requirements_resolver"] is resolver
