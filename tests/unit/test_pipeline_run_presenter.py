"""Unit tests for PipelineRunPresenter (thin UI/reporting adapter)."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from transcriptx.core.pipeline.run_presenter import PipelineRunPresenter


@pytest.mark.unit
def test_build_summary_delegates_to_output_reporter(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: Dict[str, Any] = {}

    def _fake_summary(**kwargs: Any) -> Dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True, "modules": kwargs["modules_run"]}

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_presenter.generate_comprehensive_output_summary",
        _fake_summary,
    )
    presenter = PipelineRunPresenter()
    summary = presenter.build_summary(
        transcript_path="/tmp/t.json",
        selected_modules=["stats", "ner"],
        modules_run=["stats"],
        errors=["ner failed"],
        skipped_modules=[{"module": "voice", "reason": "no audio"}],
    )
    assert summary == {"ok": True, "modules": ["stats"]}
    assert captured["transcript_path"] == "/tmp/t.json"
    assert captured["selected_modules"] == ["stats", "ner"]
    assert captured["modules_run"] == ["stats"]
    assert captured["errors"] == ["ner failed"]
    assert captured["skipped_modules"] == [{"module": "voice", "reason": "no audio"}]


@pytest.mark.unit
def test_show_pre_and_post_run_delegate(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, tuple[Any, ...]]] = []

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_presenter.print_review_before_run",
        lambda review: calls.append(("review", (review,))),
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_presenter.display_output_summary_to_user",
        lambda summary: calls.append(("display", (summary,))),
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_presenter.print_compact_post_run_summary",
        lambda output_dir, results: calls.append(("compact", (output_dir, results))),
    )

    presenter = PipelineRunPresenter()
    review = {"modules_will_run": ["stats"]}
    summary = {"modules_run": ["stats"]}
    results = {"errors": []}
    presenter.show_pre_run_review(review)
    presenter.show_post_run_summary(summary, "/out", results)

    assert calls == [
        ("review", (review,)),
        ("display", (summary,)),
        ("compact", ("/out", results)),
    ]
