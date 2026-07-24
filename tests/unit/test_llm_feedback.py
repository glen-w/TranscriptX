"""Unit tests for LLM feedback store, validation, and identity."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import pytest

from transcriptx.core.llm_feedback.errors import (
    LlmFeedbackPathError,
    LlmFeedbackPersistenceError,
    LlmFeedbackValidationError,
)
from transcriptx.core.llm_feedback.models import (
    EVENT_SCHEMA_ID,
    NOTE_MAX_CODEPOINTS,
    FeedbackProvenance,
    FeedbackRating,
    FeedbackReason,
    FeedbackSurface,
    FeedbackTarget,
    build_event,
    compute_output_sha256,
    compute_target_instance_id,
    normalize_note,
    reasons_for_rating,
)
from transcriptx.core.llm_feedback.service import LlmFeedbackService
from transcriptx.core.llm_feedback.store import FeedbackStore
from transcriptx.core.llm_feedback.validate import validate_event, validate_rating_reason


def _target(**overrides) -> FeedbackTarget:
    base = dict(
        surface=FeedbackSurface.INSIGHTS_BLOCK.value,
        block_id="llm_summary_block",
        placement_id="p1",
        module="llm_summary",
        run_id="run-abc",
        subject_type="transcript",
        subject_id="subj-1",
        artifact_rel_path="llm_summary/data/global/x_llm_summary.md",
        question_id=None,
        questions_hash=None,
        logical_chart_id=None,
    )
    base.update(overrides)
    return FeedbackTarget(**base)


def _event(**kwargs):
    return build_event(
        rating=kwargs.pop("rating", FeedbackRating.UP),
        reason=kwargs.pop("reason", FeedbackReason.HELPFUL),
        note=kwargs.pop("note", ""),
        output_text=kwargs.pop("output_text", "Hello summary"),
        target=kwargs.pop("target", _target()),
        provenance=kwargs.pop("provenance", FeedbackProvenance(None, None, None, None, None)),
        submission_token=kwargs.pop("submission_token", None),
        **kwargs,
    )


def test_rating_reason_matrix() -> None:
    assert FeedbackReason.HELPFUL in {
        r for r in reasons_for_rating(FeedbackRating.UP)
    }
    assert FeedbackReason.TOO_VAGUE not in set(reasons_for_rating(FeedbackRating.UP))
    validate_rating_reason("up", "other")
    validate_rating_reason("down", "other")
    with pytest.raises(LlmFeedbackValidationError):
        validate_rating_reason("up", "inaccurate")
    with pytest.raises(LlmFeedbackValidationError):
        validate_rating_reason("down", "helpful")


def test_note_normalization_and_bounds() -> None:
    assert normalize_note("  hi\r\nthere\x00  ") == "  hi\nthere"
    with pytest.raises(ValueError):
        normalize_note("x" * (NOTE_MAX_CODEPOINTS + 1))


def test_output_sha_changes_with_content() -> None:
    a = compute_output_sha256("one")
    b = compute_output_sha256("two")
    assert a != b
    assert len(a) == 64


def test_append_and_idempotent_token(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path)
    token = "11111111-1111-4111-8111-111111111111"
    ev = _event(submission_token=token)
    r1 = store.append(ev)
    assert not r1.duplicated
    r2 = store.append(ev)
    assert r2.duplicated
    assert r2.feedback_id == r1.feedback_id
    result = store.iter_events()
    assert len(result.events) == 1
    assert result.tail_error is None


def test_superseding_second_rating(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path)
    text = "same output"
    t = _target()
    e1 = build_event(
        rating="up",
        reason="helpful",
        note="",
        output_text=text,
        target=t,
        submission_token="22222222-2222-4222-8222-222222222222",
    )
    e2 = build_event(
        rating="down",
        reason="too_vague",
        note="needs more",
        output_text=text,
        target=t,
        submission_token="33333333-3333-4333-8333-333333333333",
        supersedes_feedback_id=e1.feedback_id,
    )
    store.append(e1)
    store.append(e2)
    events = store.iter_events().events
    assert len(events) == 2
    assert events[0].target_instance_id == events[1].target_instance_id
    assert events[1].rating == "down"


def test_concurrent_appends(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path)
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            ev = build_event(
                rating="up",
                reason="helpful",
                note=f"n{i}",
                output_text=f"out-{i}",
                target=_target(artifact_rel_path=f"llm_summary/a{i}.md"),
            )
            store.append(ev)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(store.iter_events().events) == 8


def test_missing_provenance_ok(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path)
    ev = _event(provenance=FeedbackProvenance(None, None, None, None, None))
    store.append(ev)
    loaded = store.iter_events().events[0]
    assert loaded.provenance.model is None
    assert loaded.provenance.output_schema_id is None


def test_unwritable_directory(tmp_path: Path) -> None:
    root = tmp_path / "ro"
    root.mkdir()
    store = FeedbackStore(root)
    # Prepare then make store dir unwritable by chmod parent state
    store._ensure_store_dir()
    os.chmod(store.store_dir, 0o500)
    try:
        with pytest.raises(LlmFeedbackPersistenceError):
            store.append(_event())
    finally:
        os.chmod(store.store_dir, 0o700)


def test_symlink_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not supported")
    with pytest.raises(LlmFeedbackPathError):
        FeedbackStore(link).append(_event())


def test_truncated_tail_preserved(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path)
    store.append(_event(output_text="first"))
    # Append a truncated line without going through the writer
    with open(store.events_path, "ab") as handle:
        handle.write(b'{"schema_id":"llm_feedback_event_v1","feedback_id":"broken')
    result = store.iter_events()
    assert len(result.events) == 1
    assert result.tail_error is not None
    # New append still works
    store.append(_event(output_text="second", submission_token="44444444-4444-4444-8444-444444444444"))
    result2 = store.iter_events()
    assert len(result2.events) >= 2
    assert result2.events[0].output_sha256 == compute_output_sha256("first")


def test_path_traversal_artifact_rejected() -> None:
    with pytest.raises(LlmFeedbackValidationError):
        validate_event(
            _event(target=_target(artifact_rel_path="../etc/passwd")).to_dict()
        )


def test_custom_qa_requires_question_identity() -> None:
    with pytest.raises(LlmFeedbackValidationError):
        validate_event(
            _event(
                target=_target(
                    surface=FeedbackSurface.CUSTOM_QA_ANSWER.value,
                    block_id="llm_custom_qa_block",
                    module="llm_custom_qa",
                    question_id=None,
                    questions_hash="abcd",
                )
            ).to_dict()
        )


def test_chart_requires_logical_id() -> None:
    with pytest.raises(LlmFeedbackValidationError):
        validate_event(
            _event(
                target=_target(
                    surface=FeedbackSurface.CHART_CAPTION.value,
                    block_id=None,
                    module="chart_descriptions",
                    artifact_rel_path=None,
                    logical_chart_id=None,
                )
            ).to_dict()
        )


def test_service_submit(tmp_path: Path) -> None:
    svc = LlmFeedbackService(data_dir=tmp_path)
    result = svc.submit(
        rating="up",
        reason="helpful",
        note="",
        output_text="svc text",
        target=_target(),
        submission_token="55555555-5555-4555-8555-555555555555",
    )
    assert not result.duplicated
    assert EVENT_SCHEMA_ID == svc.iter_events().events[0].schema_id


def test_target_instance_id_stable() -> None:
    t = _target()
    sha = compute_output_sha256("x")
    a = compute_target_instance_id(
        surface=t.surface,
        run_id=t.run_id,
        subject_type=t.subject_type,
        subject_id=t.subject_id,
        module=t.module,
        artifact_rel_path=t.artifact_rel_path,
        output_sha256=sha,
        question_id=None,
        questions_hash=None,
        logical_chart_id=None,
        block_id=t.block_id,
    )
    b = compute_target_instance_id(
        surface=t.surface,
        run_id=t.run_id,
        subject_type=t.subject_type,
        subject_id=t.subject_id,
        module=t.module,
        artifact_rel_path=t.artifact_rel_path,
        output_sha256=sha,
        question_id=None,
        questions_hash=None,
        logical_chart_id=None,
        block_id=t.block_id,
    )
    assert a == b
