"""Structured-execution tripwires and consumer inventory tests."""

from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.llm_custom_qa.consumer_registry import (
    CUSTOM_QA_CONSUMER_REGISTRY,
    activation_blocking_consumers,
)
from transcriptx.core.analysis.llm_custom_qa.questions_binding import (
    bind_custom_qa_questions,
    copy_bound_questions_to_context,
    get_bound_structured_questions,
    reset_custom_qa_questions,
)
from transcriptx.core.analysis.llm_custom_qa.resolve import (
    resolve_effective_custom_qa_questions,
)
from transcriptx.core.analysis.llm_custom_qa.versioning import (
    MODULE_VERSION,
    SCHEMA_ID,
    is_structured_execution_enabled,
    live_module_version_for_writers,
    live_schema_id_for_writers,
    set_structured_execution_enabled,
)


@pytest.fixture(autouse=True)
def _restore_structured_flag():
    prev = is_structured_execution_enabled()
    yield
    set_structured_execution_enabled(prev)


@pytest.mark.unit
def test_structured_execution_defaults_off() -> None:
    """Live writer uses the sole schema; structured execution stays off."""
    assert is_structured_execution_enabled() is False
    assert live_schema_id_for_writers() == SCHEMA_ID
    assert live_module_version_for_writers() == MODULE_VERSION
    set_structured_execution_enabled(True)
    assert is_structured_execution_enabled() is True
    set_structured_execution_enabled(False)
    assert is_structured_execution_enabled() is False


@pytest.mark.unit
def test_structured_plan_constructor_tripwire_when_disabled() -> None:
    from transcriptx.core.analysis.llm_custom_qa.plan import (
        assert_structured_execution_allowed,
    )

    set_structured_execution_enabled(False)
    with pytest.raises(RuntimeError, match="disabled"):
        assert_structured_execution_allowed()


@pytest.mark.unit
def test_activation_inventory_requires_structured_ready_blockers() -> None:
    blockers = activation_blocking_consumers()
    assert blockers
    unsafe = [c for c in blockers if not c.structured_ready]
    assert unsafe == [], f"Stage 5 blocked by unsafe consumers: {unsafe}"
    assert all(isinstance(c.consumer_id, str) for c in CUSTOM_QA_CONSUMER_REGISTRY)
    agg = next(c for c in CUSTOM_QA_CONSUMER_REGISTRY if c.role == "aggregator")
    assert agg.structured_ready is True


@pytest.mark.unit
def test_actions_placements_removed_from_presets() -> None:
    root = Path(__file__).resolve().parents[4]
    default = (root / "src/transcriptx/web/layouts/presets/default.yaml").read_text()
    executive = (
        root / "src/transcriptx/web/layouts/presets/executive.yaml"
    ).read_text()
    assert "insights_llm_custom_qa" not in default
    assert "exec_custom_qa" not in executive


@pytest.mark.unit
def test_run_from_context_does_not_touch_structured_surfaces(monkeypatch) -> None:
    """Tripwire: structured constructors must not be called on the live path."""
    set_structured_execution_enabled(False)
    calls: list[str] = []

    def boom(*_a, **_k):
        calls.append("plan")
        raise AssertionError("structured plan touched")

    monkeypatch.setattr(
        "transcriptx.core.analysis.llm_custom_qa.plan.assert_structured_execution_allowed",
        boom,
    )
    from transcriptx.core.analysis.llm_custom_qa.analyze import LLMCustomQAAnalysis
    from transcriptx.core.analysis.llm_custom_qa.resolve import (
        EffectiveCustomQAQuestions,
    )

    effective = EffectiveCustomQAQuestions(
        questions=(),
        questions_hash="x",
        empty=True,
        resolved_from="explicit_empty",
        max_questions_per_run=8,
        max_question_chars=500,
        max_run_total_question_chars=4000,
        max_answer_chars=800,
    )
    token = bind_custom_qa_questions(effective)
    try:
        ctx = MagicMock()
        ctx.transcript_path = "t.json"
        ctx.get_transcript_dir.return_value = str(
            Path(__file__).resolve().parents[4] / "tests" / "fixtures"
        )
        ctx.get_run_id.return_value = "run"
        ctx.get_runtime_flags.return_value = {}
        monkeypatch.setattr(
            "transcriptx.core.analysis.llm_custom_qa.analyze.create_output_service",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stop-before-io")),
        )
        with pytest.raises(Exception):
            LLMCustomQAAnalysis().run_from_context(ctx)
        assert calls == []
    finally:
        reset_custom_qa_questions(token)


@pytest.mark.unit
def test_bound_questions_visible_in_worker_thread() -> None:
    """ContextVar binding must be copyable into pipeline worker threads."""
    effective = resolve_effective_custom_qa_questions(
        request_questions=["What was decided?"],
        request_field_present=True,
    )
    token = bind_custom_qa_questions(effective)
    try:
        snapshot = copy_bound_questions_to_context()
        assert snapshot is not None

        def _worker() -> str | None:
            inner = bind_custom_qa_questions(snapshot)
            try:
                bound = get_bound_structured_questions()
                return None if bound is None else bound.structured[0].text
            finally:
                reset_custom_qa_questions(inner)

        ctx = contextvars.copy_context()
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(ctx.run, _worker)
            assert fut.result() == "What was decided?"
    finally:
        reset_custom_qa_questions(token)
