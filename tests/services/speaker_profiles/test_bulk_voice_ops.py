"""Contracts for Settings library-wide voice enrol / suggestion pre-load."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.services.speaker_profiles.bulk_voice_ops import (
    BulkEnrolPreview,
    BulkEnrolProfilePreview,
    BulkPreloadOccurrencePreview,
    BulkPreloadPreview,
    BulkPreloadResult,
    BulkVoiceOpsService,
    BulkVoiceTargetStatus,
)


@pytest.mark.unit
def test_speakers_panel_exports_bulk_helpers() -> None:
    from transcriptx.web.ui.settings.speakers_panel import (
        _render_bulk_voice_ops,
        render_speakers_panel,
    )

    assert callable(render_speakers_panel)
    assert callable(_render_bulk_voice_ops)


@pytest.mark.unit
def test_bulk_enrol_preview_active_only_and_actionable(monkeypatch) -> None:
    items = [
        SimpleNamespace(
            profile_id="p-active",
            display_name="Active",
            status="active",
            link_count=2,
        ),
        SimpleNamespace(
            profile_id="p-empty",
            display_name="Empty",
            status="active",
            link_count=0,
        ),
        SimpleNamespace(
            profile_id="p-arch",
            display_name="Archived",
            status="archived",
            link_count=5,
        ),
    ]
    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.bulk_voice_ops.list_profiles",
        lambda *, root: items,
    )
    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.bulk_voice_ops.list_samples_for_profile",
        lambda profile_id, *, root: (
            [SimpleNamespace(eligibility_state="eligible")]
            if profile_id == "p-active"
            else []
        ),
    )
    barrier = MagicMock()
    barrier.assert_processing_allowed = MagicMock()
    facade = MagicMock()
    svc = BulkVoiceOpsService(root=Path("/tmp"), facade=facade)
    svc.barrier = barrier

    preview = svc.preview_enrol_all_profiles()
    barrier.assert_processing_allowed.assert_called_once()
    assert preview.profile_count == 2
    assert preview.with_confirmed_links == 1
    assert preview.without_confirmed_links == 1
    assert preview.with_eligible_samples == 1
    assert preview.actionable_count == 1
    assert [t.profile_id for t in preview.targets] == ["p-active", "p-empty"]


@pytest.mark.unit
def test_bulk_enrol_execute_skips_empty_and_isolates_errors(monkeypatch) -> None:
    items = [
        SimpleNamespace(
            profile_id="p-ok",
            display_name="Ok",
            status="active",
            link_count=1,
        ),
        SimpleNamespace(
            profile_id="p-skip",
            display_name="Skip",
            status="active",
            link_count=0,
        ),
        SimpleNamespace(
            profile_id="p-err",
            display_name="Err",
            status="active",
            link_count=1,
        ),
    ]
    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.bulk_voice_ops.list_profiles",
        lambda *, root: items,
    )
    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.bulk_voice_ops.list_samples_for_profile",
        lambda profile_id, *, root: [],
    )

    facade = MagicMock()

    def _enrol(*, operation_idempotency_key, profile_id):
        if profile_id == "p-err":
            raise RuntimeError("boom")
        return SimpleNamespace(
            links_attempted=1,
            links_enrolled=1,
            sample_ids=("s1",),
        )

    facade.bootstrap_enrol_profile.side_effect = _enrol
    svc = BulkVoiceOpsService(root=Path("/tmp"), facade=facade)
    barrier = MagicMock()
    barrier.assert_processing_allowed = MagicMock()
    svc.barrier = barrier

    progress = []
    result = svc.enrol_all_profiles(
        operation_idempotency_key="base",
        progress_callback=lambda i, t, n: progress.append((i, t, n)),
    )
    assert len(progress) == 3
    assert result.ok_count == 1
    assert result.skipped_count == 1
    assert result.error_count == 1
    assert result.links_enrolled_total == 1
    assert result.samples_total == 1
    by_id = {t.profile_id: t for t in result.targets}
    assert by_id["p-ok"].status is BulkVoiceTargetStatus.OK
    assert by_id["p-skip"].status is BulkVoiceTargetStatus.SKIPPED
    assert by_id["p-err"].status is BulkVoiceTargetStatus.ERROR
    assert "boom" in by_id["p-err"].message


@pytest.mark.unit
def test_bulk_preload_skips_ignored_and_collision(monkeypatch) -> None:
    resolved = SimpleNamespace(
        managed_transcript_id="mt-1",
        transcript_path="/lib/t1.json",
        current_relpath="t1.json",
    )
    resolver = MagicMock()
    resolver.list_admitted.return_value = [resolved]

    occs = [
        SimpleNamespace(local_speaker_key="spk_0", collision=False),
        SimpleNamespace(local_speaker_key="spk_1", collision=False),
        SimpleNamespace(local_speaker_key="spk_2", collision=True),
    ]
    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.bulk_voice_ops.discover_occurrences_for_resolved",
        lambda _resolved: occs,
    )
    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.bulk_voice_ops._ignored_keys_for_path",
        lambda _path: {"spk_1"},
    )
    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.bulk_voice_ops.load_transcript_segments",
        lambda _path: [{"speaker": "spk_0", "text": "hi"}],
    )

    facade = MagicMock()
    facade.analyse.return_value = SimpleNamespace(
        outcome="SuggestionAvailable", detail=None
    )
    svc = BulkVoiceOpsService(root=Path("/tmp"), facade=facade, resolver=resolver)
    barrier = MagicMock()
    barrier.assert_processing_allowed = MagicMock()
    svc.barrier = barrier

    preview = svc.preview_preload_suggestions()
    assert preview.transcript_count == 1
    assert preview.occurrence_count == 3
    assert preview.ignored_count == 1
    assert preview.collision_count == 1
    assert preview.actionable_count == 1

    result = svc.preload_suggestions()
    assert result.ok_count == 1
    assert result.skipped_count == 2
    assert result.suggestion_count == 1
    facade.analyse.assert_called_once()
    call_kwargs = facade.analyse.call_args.kwargs
    assert call_kwargs["raw_speaker"] == "spk_0"


@pytest.mark.unit
def test_bulk_ops_require_activation_barrier() -> None:
    from transcriptx.core.speaker_profiles.voice.errors import VoiceFeatureDisabled

    facade = MagicMock()
    svc = BulkVoiceOpsService(root=Path("/tmp"), facade=facade)
    barrier = MagicMock()
    barrier.assert_processing_allowed = MagicMock(
        side_effect=VoiceFeatureDisabled("voice matching disabled")
    )
    svc.barrier = barrier

    with pytest.raises(VoiceFeatureDisabled):
        svc.preview_enrol_all_profiles()
    with pytest.raises(VoiceFeatureDisabled):
        svc.preview_preload_suggestions()
    facade.bootstrap_enrol_profile.assert_not_called()
    facade.analyse.assert_not_called()


@pytest.mark.unit
def test_bulk_preload_progress_and_error_isolation(monkeypatch) -> None:
    resolved = SimpleNamespace(
        managed_transcript_id="mt-1",
        transcript_path="/lib/meet.json",
        current_relpath="meet.json",
    )
    resolver = MagicMock()
    resolver.list_admitted.return_value = [resolved]
    occs = [
        SimpleNamespace(local_speaker_key="spk_0", collision=False),
        SimpleNamespace(local_speaker_key="spk_1", collision=False),
    ]
    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.bulk_voice_ops.discover_occurrences_for_resolved",
        lambda _resolved: occs,
    )
    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.bulk_voice_ops._ignored_keys_for_path",
        lambda _path: set(),
    )
    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.bulk_voice_ops.load_transcript_segments",
        lambda _path: [{"speaker": "spk_0"}],
    )

    facade = MagicMock()

    def _analyse(*, transcript_path, raw_speaker, segments):
        if raw_speaker == "spk_1":
            raise RuntimeError("embed boom")
        return SimpleNamespace(outcome="NoReliableMatch", detail=None)

    facade.analyse.side_effect = _analyse
    svc = BulkVoiceOpsService(root=Path("/tmp"), facade=facade, resolver=resolver)
    barrier = MagicMock()
    barrier.assert_processing_allowed = MagicMock()
    svc.barrier = barrier

    progress: list[tuple[int, int, str]] = []
    result = svc.preload_suggestions(
        progress_callback=lambda i, t, n: progress.append((i, t, n))
    )
    assert progress == [
        (1, 2, "meet / spk_0"),
        (2, 2, "meet / spk_1"),
    ]
    assert result.ok_count == 1
    assert result.error_count == 1
    assert result.no_match_count == 1
    by_key = {t.local_speaker_key: t for t in result.targets}
    assert by_key["spk_0"].status is BulkVoiceTargetStatus.OK
    assert by_key["spk_1"].status is BulkVoiceTargetStatus.ERROR
    assert "embed boom" in by_key["spk_1"].message


@pytest.mark.unit
def test_speakers_panel_bulk_ops_refresh_and_execute(monkeypatch) -> None:
    import transcriptx.web.ui.settings.speakers_panel as mod
    from streamlit.runtime.scriptrunner import RerunData, RerunException

    enrol_preview = BulkEnrolPreview(
        profile_count=1,
        with_confirmed_links=1,
        without_confirmed_links=0,
        with_eligible_samples=0,
        actionable_count=1,
        targets=[
            BulkEnrolProfilePreview(
                profile_id="p1",
                display_name="Ada",
                link_count=2,
                eligible_sample_count=0,
                actionable=True,
            )
        ],
    )
    preload_preview = BulkPreloadPreview(
        transcript_count=1,
        occurrence_count=1,
        ignored_count=0,
        collision_count=0,
        actionable_count=1,
        targets=[
            BulkPreloadOccurrencePreview(
                managed_transcript_id="mt",
                transcript_path="/t.json",
                transcript_label="t",
                local_speaker_key="spk_0",
                actionable=True,
            )
        ],
    )
    enrol_result = SimpleNamespace(
        ok_count=1,
        skipped_count=0,
        error_count=0,
        links_enrolled_total=1,
        samples_total=2,
        targets=[],
    )
    preload_result = BulkPreloadResult(targets=[])

    bulk = MagicMock()
    bulk.preview_enrol_all_profiles.return_value = enrol_preview
    bulk.enrol_all_profiles.return_value = enrol_result
    bulk.preview_preload_suggestions.return_value = preload_preview
    bulk.preload_suggestions.return_value = preload_result
    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.bulk_voice_ops.BulkVoiceOpsService",
        lambda: bulk,
    )

    class _St:
        session_state: dict = {
            mod._ENROL_PREVIEW_KEY: enrol_preview,
            mod._PRELOAD_PREVIEW_KEY: preload_preview,
        }
        button_kwargs: list[dict] = []
        clicked: set[str] = set()

        def subheader(self, *_a, **_k):
            return None

        def markdown(self, *_a, **_k):
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

        def button(self, label, **kwargs):
            self.button_kwargs.append({"label": label, **kwargs})
            key = str(kwargs.get("key") or label)
            return key in self.clicked

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

        def progress(self, *_a, **_k):
            class _P:
                def progress(self, *_a, **_k):
                    return None

            return _P()

        def empty(self):
            return self

        def rerun(self):
            raise RerunException(RerunData())

    st = _St()
    monkeypatch.setattr(mod, "st", st)

    # Inventory already present: execute enrol when button clicked.
    st.clicked = {"voice_bulk_enrol_all_btn"}
    with pytest.raises(RerunException):
        mod._render_bulk_voice_ops()
    bulk.enrol_all_profiles.assert_called_once()
    assert mod._ENROL_RESULT_KEY in st.session_state

    # Reset and execute preload.
    st.session_state = {
        mod._ENROL_PREVIEW_KEY: enrol_preview,
        mod._PRELOAD_PREVIEW_KEY: preload_preview,
    }
    st.clicked = {"voice_bulk_preload_btn"}
    bulk.reset_mock()
    with pytest.raises(RerunException):
        mod._render_bulk_voice_ops()
    bulk.preload_suggestions.assert_called_once()
    assert mod._PRELOAD_RESULT_KEY in st.session_state

    labels = {b["label"] for b in st.button_kwargs}
    assert "Enrol trusted voice for all profiles" in labels
    assert "Pre-load voice suggestions" in labels
