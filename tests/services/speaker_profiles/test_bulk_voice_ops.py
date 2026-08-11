"""Contracts for Settings library-wide voice enrol / suggestion pre-load."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.services.speaker_profiles.bulk_voice_ops import (
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
