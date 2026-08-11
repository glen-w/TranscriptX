"""Contracts for Settings bulk correction-candidate generation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.services.corrections_studio.bulk_generation import (
    CONFIRM_REGENERATE_ALL,
    BulkCorrectionsGenerationService,
    BulkGenerationMode,
    BulkGenerationResult,
    BulkTargetStatus,
)
from transcriptx.services.corrections_studio.candidate_service import (
    GenerateCandidatesResult,
)


@pytest.mark.unit
def test_settings_page_includes_corrections_tab() -> None:
    src = Path("src/transcriptx/web/page_modules/settings.py").read_text(
        encoding="utf-8"
    )
    assert "Corrections" in src
    assert "render_corrections_panel" in src


@pytest.mark.unit
def test_corrections_panel_exports_render() -> None:
    from transcriptx.web.ui.settings.corrections_panel import render_corrections_panel

    assert callable(render_corrections_panel)


@pytest.mark.unit
def test_regenerate_confirm_phrase_is_exact() -> None:
    assert CONFIRM_REGENERATE_ALL == "REGENERATE ALL"


@pytest.mark.unit
def test_bulk_preview_counts_missing_and_existing() -> None:
    svc = MagicMock()
    svc.list_transcript_summaries_for_studio.return_value = [
        SimpleNamespace(path="/t/a.json", base_name="a"),
        SimpleNamespace(path="/t/b.json", base_name="b"),
        SimpleNamespace(path="/t/c.json", base_name="c"),
    ]
    by_path = {
        "/t/a.json": {"candidates": [{"id": "1"}]},
        "/t/b.json": None,
        "/t/c.json": {"candidates": []},
    }
    store = MagicMock()
    store.read.side_effect = lambda path: by_path[path]
    bulk = BulkCorrectionsGenerationService(service=svc, store=store)

    preview = bulk.preview(BulkGenerationMode.GENERATE_MISSING)
    assert preview.transcript_count == 3
    assert preview.with_candidates == 1
    assert preview.without_candidates == 2
    assert preview.actionable_count == 2

    regenerate = bulk.preview(BulkGenerationMode.REGENERATE_ALL)
    assert regenerate.actionable_count == 3


@pytest.mark.unit
def test_bulk_execute_generate_missing_skips_existing() -> None:
    svc = MagicMock()
    svc.list_transcript_summaries_for_studio.return_value = [
        SimpleNamespace(path="/t/a.json", base_name="a"),
        SimpleNamespace(path="/t/b.json", base_name="b"),
    ]
    store = MagicMock()
    store.read.side_effect = [
        {"candidates": [{"id": "1"}, {"id": "2"}]},
        None,
    ]
    session = SimpleNamespace(session_id="sid-b", candidates=[])
    svc.start_or_resume_session.return_value = session
    svc.generate_candidates.return_value = GenerateCandidatesResult(
        candidates=[SimpleNamespace(id="n1")]
    )
    bulk = BulkCorrectionsGenerationService(service=svc, store=store)

    result = bulk.execute(BulkGenerationMode.GENERATE_MISSING)
    assert isinstance(result, BulkGenerationResult)
    assert result.skipped_count == 1
    assert result.generated_count == 1
    assert result.error_count == 0
    svc.start_or_resume_session.assert_called_once_with("/t/b.json")
    svc.generate_candidates.assert_called_once_with("sid-b", force=False)


@pytest.mark.unit
def test_bulk_execute_regenerate_forces_all() -> None:
    svc = MagicMock()
    svc.list_transcript_summaries_for_studio.return_value = [
        SimpleNamespace(path="/t/a.json", base_name="a"),
    ]
    store = MagicMock()
    store.read.return_value = {"candidates": [{"id": "1"}]}
    svc.start_or_resume_session.return_value = SimpleNamespace(
        session_id="sid-a", candidates=[SimpleNamespace(id="1")]
    )
    svc.generate_candidates.return_value = GenerateCandidatesResult(
        candidates=[SimpleNamespace(id="1"), SimpleNamespace(id="2")]
    )
    progress: list[tuple[int, int, str]] = []
    bulk = BulkCorrectionsGenerationService(service=svc, store=store)

    result = bulk.execute(
        BulkGenerationMode.REGENERATE_ALL,
        progress_callback=lambda i, t, n: progress.append((i, t, n)),
    )
    assert result.generated_count == 1
    assert result.targets[0].status is BulkTargetStatus.GENERATED
    assert result.targets[0].candidate_count == 2
    svc.generate_candidates.assert_called_once_with("sid-a", force=True)
    assert progress == [(1, 1, "a")]


@pytest.mark.unit
def test_bulk_execute_records_errors() -> None:
    svc = MagicMock()
    svc.list_transcript_summaries_for_studio.return_value = [
        SimpleNamespace(path="/t/bad.json", base_name="bad"),
    ]
    store = MagicMock()
    store.read.return_value = None
    svc.start_or_resume_session.side_effect = RuntimeError("boom")
    bulk = BulkCorrectionsGenerationService(service=svc, store=store)

    result = bulk.execute(BulkGenerationMode.GENERATE_MISSING)
    assert result.error_count == 1
    assert result.targets[0].status is BulkTargetStatus.ERROR
    assert "boom" in result.targets[0].message


@pytest.mark.unit
def test_bulk_execute_records_aborted_commits() -> None:
    svc = MagicMock()
    svc.list_transcript_summaries_for_studio.return_value = [
        SimpleNamespace(path="/t/a.json", base_name="a"),
    ]
    store = MagicMock()
    store.read.return_value = None
    svc.start_or_resume_session.return_value = SimpleNamespace(
        session_id="sid-a", candidates=[]
    )
    svc.generate_candidates.return_value = GenerateCandidatesResult(
        candidates=[SimpleNamespace(id="old")],
        commit_aborted=True,
        abort_reason="concurrent write",
    )
    bulk = BulkCorrectionsGenerationService(service=svc, store=store)

    result = bulk.execute(BulkGenerationMode.GENERATE_MISSING)
    assert result.aborted_count == 1
    assert result.generated_count == 0
    assert result.targets[0].status is BulkTargetStatus.ABORTED
    assert "concurrent write" in result.targets[0].message


@pytest.mark.unit
def test_bulk_execute_skips_when_session_gains_candidates() -> None:
    """Race: preview said missing, but start_or_resume already has candidates."""
    svc = MagicMock()
    svc.list_transcript_summaries_for_studio.return_value = [
        SimpleNamespace(path="/t/a.json", base_name="a"),
    ]
    store = MagicMock()
    store.read.return_value = None
    svc.start_or_resume_session.return_value = SimpleNamespace(
        session_id="sid-a",
        candidates=[SimpleNamespace(id="1")],
    )
    bulk = BulkCorrectionsGenerationService(service=svc, store=store)

    result = bulk.execute(BulkGenerationMode.GENERATE_MISSING)
    assert result.skipped_count == 1
    svc.generate_candidates.assert_not_called()


@pytest.mark.unit
def test_controller_bulk_methods_delegate() -> None:
    from transcriptx.services.corrections_studio.controller import (
        CorrectionsStudioController,
    )
    from transcriptx.services.corrections_studio.bulk_generation import (
        BulkGenerationPreview,
        BulkGenerationResult,
    )

    ctrl = CorrectionsStudioController.__new__(CorrectionsStudioController)
    preview = BulkGenerationPreview(
        mode=BulkGenerationMode.GENERATE_MISSING,
        transcript_count=0,
        with_candidates=0,
        without_candidates=0,
        actionable_count=0,
    )
    outcome = BulkGenerationResult(mode=BulkGenerationMode.GENERATE_MISSING)
    bulk = MagicMock()
    bulk.preview.return_value = preview
    bulk.execute.return_value = outcome
    ctrl._bulk = bulk

    assert ctrl.preview_bulk_candidate_generation(
        BulkGenerationMode.GENERATE_MISSING
    ) is preview
    assert (
        ctrl.run_bulk_candidate_generation(BulkGenerationMode.REGENERATE_ALL)
        is outcome
    )
    bulk.preview.assert_called_once_with(BulkGenerationMode.GENERATE_MISSING)
    bulk.execute.assert_called_once_with(
        BulkGenerationMode.REGENERATE_ALL, progress_callback=None
    )


@pytest.mark.unit
def test_corrections_panel_regenerate_requires_confirm(monkeypatch) -> None:
    import transcriptx.web.ui.settings.corrections_panel as mod
    from transcriptx.services.corrections_studio.bulk_generation import (
        BulkGenerationPreview,
        BulkGenerationTargetPreview,
    )

    preview = BulkGenerationPreview(
        mode=BulkGenerationMode.REGENERATE_ALL,
        transcript_count=1,
        with_candidates=1,
        without_candidates=0,
        actionable_count=1,
        targets=[
            BulkGenerationTargetPreview(
                path="/t/a.json",
                base_name="a",
                has_candidates=True,
                candidate_count=1,
            )
        ],
    )
    controller = MagicMock()
    monkeypatch.setattr(mod, "CorrectionsStudioController", lambda: controller)

    class _St:
        session_state = {
            "_corrections_bulk_preview": preview,
            "_corrections_bulk_mode": BulkGenerationMode.REGENERATE_ALL.value,
        }
        button_kwargs: list[dict] = []

        def subheader(self, *_a, **_k):
            return None

        def caption(self, *_a, **_k):
            return None

        def info(self, *_a, **_k):
            return None

        def success(self, *_a, **_k):
            return None

        def warning(self, *_a, **_k):
            return None

        def error(self, *_a, **_k):
            return None

        def radio(self, *_a, **_k):
            return "Regenerate all"

        def button(self, label, **kwargs):
            self.button_kwargs.append({"label": label, **kwargs})
            return False

        def columns(self, n):
            class _Col:
                def metric(self, *_a, **_k):
                    return None

            return [_Col() for _ in range(n)]

        def expander(self, *_a, **_k):
            class _Exp:
                def __enter__(self):
                    return self

                def __exit__(self, *_a):
                    return False

            return _Exp()

        def dataframe(self, *_a, **_k):
            return None

        def checkbox(self, *_a, **_k):
            return False

        def text_input(self, *_a, **_k):
            return ""

        def progress(self, *_a, **_k):
            return None

        def empty(self):
            return self

        def rerun(self):
            return None

    st = _St()
    monkeypatch.setattr(mod, "st", st)
    mod.render_corrections_panel()

    execute_btns = [
        b for b in st.button_kwargs if b["label"] == "Regenerate all candidates"
    ]
    assert execute_btns
    assert execute_btns[0].get("disabled") is True
    controller.run_bulk_candidate_generation.assert_not_called()


@pytest.mark.unit
def test_corrections_panel_refresh_and_generate_missing(monkeypatch) -> None:
    import transcriptx.web.ui.settings.corrections_panel as mod
    from transcriptx.services.corrections_studio.bulk_generation import (
        BulkGenerationTargetPreview,
        BulkGenerationTargetResult,
        BulkGenerationPreview,
    )

    preview = BulkGenerationPreview(
        mode=BulkGenerationMode.GENERATE_MISSING,
        transcript_count=2,
        with_candidates=1,
        without_candidates=1,
        actionable_count=1,
        targets=[
            BulkGenerationTargetPreview(
                path="/t/a.json",
                base_name="a",
                has_candidates=True,
                candidate_count=3,
            ),
            BulkGenerationTargetPreview(
                path="/t/b.json",
                base_name="b",
                has_candidates=False,
                candidate_count=0,
            ),
        ],
    )
    result = BulkGenerationResult(
        mode=BulkGenerationMode.GENERATE_MISSING,
        targets=[
            BulkGenerationTargetResult(
                path="/t/b.json",
                base_name="b",
                status=BulkTargetStatus.GENERATED,
                candidate_count=2,
            )
        ],
    )

    controller = MagicMock()
    controller.preview_bulk_candidate_generation.return_value = preview
    controller.run_bulk_candidate_generation.return_value = result
    monkeypatch.setattr(mod, "CorrectionsStudioController", lambda: controller)

    class _Progress:
        def progress(self, *_a, **_k):
            return None

    class _St:
        session_state = {
            "_corrections_bulk_preview": preview,
            "_corrections_bulk_mode": BulkGenerationMode.GENERATE_MISSING.value,
        }
        button_returns = {"Generate missing candidates": True}
        infos: list[str] = []
        successes: list[str] = []
        rerun_calls = 0

        def subheader(self, *_a, **_k):
            return None

        def caption(self, *_a, **_k):
            return None

        def info(self, msg, **_k):
            self.infos.append(str(msg))

        def success(self, msg, **_k):
            self.successes.append(str(msg))

        def warning(self, *_a, **_k):
            return None

        def error(self, *_a, **_k):
            return None

        def radio(self, *_a, **_k):
            return "Generate missing"

        def button(self, label, **_k):
            return bool(self.button_returns.get(label, False))

        def columns(self, n):
            class _Col:
                def metric(self, *_a, **_k):
                    return None

            return [_Col() for _ in range(n)]

        def expander(self, *_a, **_k):
            class _Exp:
                def __enter__(self):
                    return self

                def __exit__(self, *_a):
                    return False

                def dataframe(self, *_a, **_k):
                    return None

                def caption(self, *_a, **_k):
                    return None

                def text(self, *_a, **_k):
                    return None

                def error(self, *_a, **_k):
                    return None

                def warning(self, *_a, **_k):
                    return None

            return _Exp()

        def dataframe(self, *_a, **_k):
            return None

        def progress(self, *_a, **_k):
            return _Progress()

        def empty(self):
            class _Empty:
                def caption(self, *_a, **_k):
                    return None

            return _Empty()

        def checkbox(self, *_a, **_k):
            return False

        def text_input(self, *_a, **_k):
            return ""

        def rerun(self):
            self.rerun_calls += 1

    st = _St()
    monkeypatch.setattr(mod, "st", st)
    mod.render_corrections_panel()

    controller.run_bulk_candidate_generation.assert_called_once()
    args, kwargs = controller.run_bulk_candidate_generation.call_args
    assert args[0] is BulkGenerationMode.GENERATE_MISSING
    assert "progress_callback" in kwargs
    assert "_corrections_bulk_last_result" in st.session_state
    assert st.rerun_calls == 1
