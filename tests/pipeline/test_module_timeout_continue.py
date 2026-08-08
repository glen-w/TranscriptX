"""Regression guards: BERTopic hang/timeout must not stall the rest of the DAG.

Captures the Ana phd full-run failure mode where:
1. ``timeout_seconds`` was registry metadata only (never enforced)
2. a hung BERTopic fit blocked every later module
3. OpenMP oversubscription contributed to native hangs
"""

from __future__ import annotations

import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import transcriptx.core.pipeline.dag_pipeline_execution as execution_module
from transcriptx.core.pipeline.dag_execution_adapter import (
    _resolve_module_timeout_seconds,
    execute_single_module,
)
from transcriptx.core.pipeline.dag_pipeline_types import ModuleExecOutcome
from transcriptx.core.pipeline.module_registry import (
    get_module_info,
    get_module_registry,
)
from transcriptx.core.utils.config.main import TranscriptXConfig


@pytest.mark.unit
def test_bertopic_registry_timeout_is_generous_and_wired_into_definitions() -> None:
    info = get_module_info("bertopic")
    assert info is not None
    assert info.timeout_seconds >= 3600
    # Spec must declare the budget (not the hardcoded ModuleInfo default of 600).
    from transcriptx.core.pipeline.module_specs.topics import (
        build_topics_module_definitions,
    )

    defs = build_topics_module_definitions(default_requirements=[])
    assert int(defs["bertopic"]["timeout_seconds"]) >= 3600


@pytest.mark.unit
def test_no_module_depends_on_bertopic() -> None:
    """A timed-out/failed bertopic must not block others via missing deps."""
    registry = get_module_registry()
    dependents = [
        name
        for name, info in registry._modules.items()
        if "bertopic" in (info.dependencies or [])
    ]
    assert dependents == []


@pytest.mark.unit
def test_resolve_module_timeout_prefers_bertopic_config() -> None:
    node = SimpleNamespace(timeout_seconds=3600)
    cfg = TranscriptXConfig()
    cfg.analysis.bertopic.timeout_seconds = 90.0
    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        assert _resolve_module_timeout_seconds("bertopic", node) == 90
    assert _resolve_module_timeout_seconds("wordclouds", node) == 3600


@pytest.mark.unit
def test_module_timeout_error_does_not_abort_pipeline() -> None:
    """``module_timeout`` is not a speaker-map critical abort."""
    from transcriptx.core.pipeline.dag_pipeline import DAGPipeline

    pipeline = DAGPipeline.__new__(DAGPipeline)
    pipeline.logger = MagicMock()
    results: dict = {}
    outcome = ModuleExecOutcome(
        status="failed",
        error=(
            "Module 'bertopic' timed out after 3600s; "
            "abandoning this module and continuing the pipeline"
        ),
        module_result={
            "error": {
                "error_code": "module_timeout",
                "error_message": "timed out",
            }
        },
    )
    assert pipeline._should_abort_pipeline(outcome, results) is False
    assert results.get("status") != "failed"


@pytest.mark.unit
def test_module_timeout_returns_failed_and_does_not_block_caller() -> None:
    class _SlowModule:
        def run_from_context(self, _context):
            time.sleep(5.0)
            return {"status": "success", "payload": {}}

    pipeline = SimpleNamespace(
        logger=MagicMock(),
        _module_progress_heartbeat=lambda *_a, **_k: None,
    )
    node = SimpleNamespace(
        function=_SlowModule,
        description="Slow module",
        requirements=[],
        timeout_seconds=1,
    )
    started = time.perf_counter()
    outcome = execute_single_module(
        pipeline,
        module_name="slow_test_module",
        node=node,
        transcript_path="/tmp/t.json",
        context=object(),
        requirements_resolver=None,
        named_speaker_count=2,
    )
    elapsed = time.perf_counter() - started
    assert elapsed < 3.0
    assert outcome.status == "failed"
    assert "timed out" in (outcome.error or "").lower()
    assert outcome.module_result is not None
    assert outcome.module_result["error"]["error_code"] == "module_timeout"


@pytest.mark.unit
def test_module_timeout_zero_means_unlimited() -> None:
    class _QuickModule:
        def run_from_context(self, _context):
            return {
                "status": "success",
                "module_name": "quick",
                "payload": {},
            }

    pipeline = SimpleNamespace(
        logger=MagicMock(),
        _module_progress_heartbeat=lambda *_a, **_k: None,
    )
    node = SimpleNamespace(
        function=_QuickModule,
        description="Quick module",
        requirements=[],
        timeout_seconds=0,
    )
    outcome = execute_single_module(
        pipeline,
        module_name="quick_test_module",
        node=node,
        transcript_path="/tmp/t.json",
        context=object(),
        requirements_resolver=None,
        named_speaker_count=2,
    )
    assert outcome.status == "success"


@pytest.mark.unit
def test_timeout_worker_inherits_bound_run_writer_lease(tmp_path) -> None:
    """Worker thread must see orchestrator lease (copy_context), else saves deadlock."""
    import contextvars
    import concurrent.futures

    from transcriptx.core.utils.run_writer_locks import (
        bind_run_writer_lease,
        get_bound_run_writer_lease,
        per_run_lock,
    )

    run = tmp_path / "run"
    run.mkdir()
    seen: list[object] = []

    def _probe() -> None:
        seen.append(get_bound_run_writer_lease())

    with per_run_lock(run) as lock:
        with bind_run_writer_lease(lock.lease()):
            ctx = contextvars.copy_context()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                ex.submit(ctx.run, _probe).result(timeout=5)

    assert len(seen) == 1
    assert seen[0] is not None
    assert seen[0].canonical_run_root  # type: ignore[union-attr]


@pytest.mark.unit
def test_hung_bertopic_timeout_allows_later_modules_in_sequential_phase() -> None:
    """End-to-end: hung bertopic times out; wordclouds still executes."""

    class _HungBertopic:
        def run_from_context(self, _context):
            time.sleep(5.0)
            return {"status": "success", "payload": {}}

    class _Wordclouds:
        def run_from_context(self, _context):
            return {
                "status": "success",
                "module_name": "wordclouds",
                "payload": {"ok": True},
            }

    class _Pipeline:
        def __init__(self) -> None:
            self.logger = MagicMock()
            self.nodes = {
                "bertopic": SimpleNamespace(
                    name="bertopic",
                    function=_HungBertopic,
                    description="BERTopic",
                    requirements=[],
                    timeout_seconds=1,
                ),
                "wordclouds": SimpleNamespace(
                    name="wordclouds",
                    function=_Wordclouds,
                    description="Wordclouds",
                    requirements=[],
                    timeout_seconds=30,
                ),
            }
            self.modules_run_seed: list[str] = ["insight_eligibility"]

        def _module_progress_heartbeat(self, *_a, **_k) -> None:
            return None

        def _check_missing_dependencies(self, _node, _modules_run):
            return []

        def _execute_single_module(self, **kwargs):
            kwargs.pop("run_report", None)
            return execute_single_module(self, **kwargs)

        def _reduce_module_outcome(self, *, module_name, outcome, results):
            if outcome.status == "success":
                results["modules_run"].append(module_name)
            elif outcome.status == "failed":
                results.setdefault("modules_failed", []).append(
                    {"module": module_name, "error": outcome.error}
                )

        def _apply_module_side_effects(self, **_kwargs):
            return None

        def _should_abort_pipeline(self, outcome, _results):
            # Mirror production: module_timeout is not critical.
            if outcome.status != "failed" or not outcome.error:
                return False
            return "speaker map" in str(outcome.error).lower()

    pipeline = _Pipeline()
    results = {
        "modules_run": list(pipeline.modules_run_seed),
        "skipped_modules": [],
        "modules_failed": [],
    }
    emitted: list[dict] = []
    cfg = TranscriptXConfig()
    cfg.analysis.bertopic.timeout_seconds = 1.0
    started = time.perf_counter()
    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        aborted, total, completed, skipped, failed, abort_error = (
            execution_module.run_sequential_execution_phase(
                pipeline,
                execution_order=["bertopic", "wordclouds"],
                results=results,
                context=object(),
                transcript_path="/tmp/t.json",
                run_report=None,
                requirements_resolver=None,
                named_speaker_count_ref=[2],
                emit=lambda event: emitted.append(event),
            )
        )
    elapsed = time.perf_counter() - started

    assert elapsed < 3.5
    assert aborted is False
    assert abort_error is None
    assert total == 2
    assert failed == 1
    assert completed == 1
    assert skipped == 0
    assert "wordclouds" in results["modules_run"]
    assert results["modules_failed"][0]["module"] == "bertopic"
    assert "timed out" in (results["modules_failed"][0]["error"] or "").lower()
    events = [e["event"] for e in emitted]
    assert events == [
        "run_started",
        "module_started",
        "module_failed",
        "module_started",
        "module_completed",
    ]
    failed_event = next(e for e in emitted if e["event"] == "module_failed")
    assert failed_event["module_name"] == "bertopic"
    assert failed_event.get("error_code") == "module_timeout"


@pytest.mark.unit
def test_pipeline_native_thread_defaults_use_setdefault(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset OMP/MKL pins to 1; explicit user values are preserved."""
    from transcriptx.core.pipeline import pipeline as pipeline_mod
    from transcriptx.core.utils.native_threads import _NATIVE_THREAD_ENV_DEFAULTS

    for key, _ in _NATIVE_THREAD_ENV_DEFAULTS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OMP_NUM_THREADS", "8")

    pipeline_mod._ensure_tokenizers_parallelism()

    assert os.environ["OMP_NUM_THREADS"] == "8"  # preserved
    assert os.environ["MKL_NUM_THREADS"] == "1"
    assert os.environ["OPENBLAS_NUM_THREADS"] == "1"
    assert os.environ["NUMBA_NUM_THREADS"] == "1"
    assert os.environ["TOKENIZERS_PARALLELISM"] == "false"


@pytest.mark.unit
def test_bertopic_analyze_uses_isolated_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fit path must use subprocess isolation (macOS native-crash mitigation)."""
    from transcriptx.core.analysis.bertopic.analysis import BERTopicAnalysis
    from transcriptx.core.utils.bertopic_fit.isolated import IsolatedFitResult

    called: list[int] = []

    def _fake_isolated(texts, _cfg, timeout_seconds=None):
        called.append(len(texts))
        return IsolatedFitResult(
            ok=True,
            topic_assignments=[0] * len(texts),
            topic_probs=None,
            topics=[
                {
                    "topic_id": 0,
                    "words": ["alpha", "beta"],
                    "weights": [0.5, 0.4],
                    "label": "alpha, beta",
                    "size": 5,
                }
            ],
            duration_seconds=0.01,
        )

    monkeypatch.setattr(
        "transcriptx.core.utils.bertopic_fit.fit_bertopic_isolated",
        _fake_isolated,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.prepare_text_data",
        lambda segments, return_indices=False: (
            ["alpha beta gamma"] * 5,
            ["A"] * 5,
            [0.0] * 5,
            list(range(5)),
        ),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.evaluate_bertopic_eligibility",
        lambda texts: SimpleNamespace(
            eligible=True, documents_count=len(texts), total_chars=100, reason=None
        ),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.verify_bertopic_import",
        lambda auto_install=False: (SimpleNamespace(BERTopic=object), None),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.embedding_model_policy_check",
        lambda _m: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.build_doc_topic_data",
        lambda **_k: ([], {"texts_count": 5}),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.build_provenance",
        lambda **_k: {},
    )
    cfg = TranscriptXConfig()
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.get_config",
        lambda: cfg,
    )

    result = BERTopicAnalysis().analyze(
        [{"text": "alpha beta gamma", "speaker": "A"}] * 5
    )
    assert not result.get("error")
    assert called == [5]
    assert result.get("topics")


@pytest.mark.unit
def test_bertopic_soft_fails_zero_sample_fit_collapse(monkeypatch) -> None:
    """Mini corpora that collapse during auto-reduce must not raise."""
    from transcriptx.core.analysis.bertopic.analysis import BERTopicAnalysis
    from transcriptx.core.utils.bertopic_fit.isolated import IsolatedFitResult

    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.verify_bertopic_import",
        lambda **_k: (SimpleNamespace(BERTopic=object), None),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.evaluate_bertopic_eligibility",
        lambda _texts: SimpleNamespace(
            eligible=True, documents_count=5, total_chars=100, reason=None
        ),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.get_config",
        lambda: TranscriptXConfig(),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.prepare_text_data",
        lambda _segs, return_indices=False: (
            ["a"] * 5,
            ["A"] * 5,
            [None] * 5,
            list(range(5)),
        ),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.bertopic_fit.fit_bertopic_isolated",
        lambda *_a, **_k: IsolatedFitResult(
            ok=False,
            topic_assignments=[],
            topic_probs=None,
            topics=[],
            duration_seconds=0.01,
            error=(
                "ValueError: Found array with 0 sample(s) (shape=(0, 768)) "
                "while a minimum of 1 is required."
            ),
            exit_code=1,
        ),
    )

    result = BERTopicAnalysis().analyze([{"text": "alpha", "speaker": "A"}] * 5)
    assert result.get("error") == "insufficient_data_after_fit"
    assert result.get("topics") == []
    assert (result.get("meta") or {}).get("reason") == "insufficient_data_after_fit"


@pytest.mark.unit
def test_bertopic_soft_fails_native_crash_from_isolated_fit(monkeypatch) -> None:
    """SIGSEGV in the fit worker must soft-fail the module, not raise."""
    from transcriptx.core.analysis.bertopic.analysis import BERTopicAnalysis
    from transcriptx.core.utils.bertopic_fit.isolated import IsolatedFitResult

    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.verify_bertopic_import",
        lambda **_k: (SimpleNamespace(BERTopic=object), None),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.evaluate_bertopic_eligibility",
        lambda _texts: SimpleNamespace(
            eligible=True, documents_count=5, total_chars=100, reason=None
        ),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.get_config",
        lambda: TranscriptXConfig(),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.embedding_model_policy_check",
        lambda _m: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.bertopic.analysis.prepare_text_data",
        lambda _segs, return_indices=False: (
            ["a"] * 5,
            ["A"] * 5,
            [None] * 5,
            list(range(5)),
        ),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.bertopic_fit.fit_bertopic_isolated",
        lambda *_a, **_k: IsolatedFitResult(
            ok=False,
            topic_assignments=[],
            topic_probs=None,
            topics=[],
            duration_seconds=0.5,
            error="bertopic_native_crash:exit=-11 signal=11",
            exit_code=-11,
        ),
    )

    result = BERTopicAnalysis().analyze([{"text": "alpha", "speaker": "A"}] * 5)
    assert result.get("error") == "native_crash"
    assert (result.get("meta") or {}).get("reason") == "native_crash"
    assert (result.get("meta") or {}).get("exit_code") == -11


@pytest.mark.unit
def test_fit_isolated_maps_nonzero_exit_to_native_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from transcriptx.core.utils.bertopic_fit import isolated as fi

    class _Completed:
        returncode = -11
        stdout = ""
        stderr = "Segmentation fault"

    monkeypatch.setattr(
        fi.subprocess,
        "run",
        lambda *_a, **_k: _Completed(),
    )
    out = fi.fit_bertopic_isolated(["doc one", "doc two"] * 3, None)
    assert out.ok is False
    assert out.exit_code == -11
    assert out.error and out.error.startswith("bertopic_native_crash")
