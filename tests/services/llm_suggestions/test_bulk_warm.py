"""Library-wide assistive LLM suggestion warm."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.services.llm_suggestions.bulk_warm import (
    BulkLlmSuggestionsService,
    BulkWarmKind,
    BulkWarmTargetStatus,
)
from transcriptx.core.speaker_profiles.identify.suggestions.models import (
    NameSuggestionsResult,
)

@pytest.mark.unit
def test_warm_speaker_names_skips_fresh_cache(monkeypatch, tmp_path: Path) -> None:
    tpath = tmp_path / "a.json"
    tpath.write_text("{}", encoding="utf-8")
    resolved = SimpleNamespace(
        managed_transcript_id="tx-1",
        transcript_path=tpath,
    )
    resolver = MagicMock()
    resolver.list_admitted.return_value = [resolved]
    svc = BulkLlmSuggestionsService(resolver=resolver)

    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm.load_transcript_segments",
        lambda _: [{"speaker": "A", "text": "hi"}],
    )
    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm._speaker_name_cache_fresh",
        lambda **_: True,
    )
    suggest = MagicMock()
    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm.suggest_speaker_names",
        suggest,
    )

    result = svc.warm_speaker_names()
    assert result.skipped_fresh_count == 1
    assert result.ok_count == 0
    suggest.assert_not_called()


@pytest.mark.unit
def test_warm_speaker_names_calls_suggest_when_stale(monkeypatch, tmp_path: Path) -> None:
    tpath = tmp_path / "a.json"
    tpath.write_text("{}", encoding="utf-8")
    resolved = SimpleNamespace(
        managed_transcript_id="tx-1",
        transcript_path=tpath,
    )
    resolver = MagicMock()
    resolver.list_admitted.return_value = [resolved]
    svc = BulkLlmSuggestionsService(resolver=resolver)

    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm._speaker_name_cache_fresh",
        lambda **_: False,
    )
    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm.load_transcript_segments",
        lambda _: [{"speaker": "A", "text": "hi"}],
    )
    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm.suggest_speaker_names",
        lambda *a, **k: NameSuggestionsResult(
            transcript_path=str(tpath),
            managed_transcript_id="tx-1",
            transcript_fingerprint="fp",
            status_message="ok",
        ),
    )

    result = svc.warm_speaker_names()
    assert result.ok_count == 1


@pytest.mark.unit
def test_preview_rename_skipped_when_content_mode_off(monkeypatch) -> None:
    resolver = MagicMock()
    resolver.list_admitted.return_value = [
        SimpleNamespace(
            managed_transcript_id="tx-1",
            transcript_path=Path("/lib/a.json"),
        )
    ]
    svc = BulkLlmSuggestionsService(resolver=resolver)
    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm._rename_content_mode",
        lambda: "off",
    )
    preview = svc.preview_rename()
    assert preview.actionable_count == 0
    assert preview.skipped_config_count == 1


@pytest.mark.unit
def test_warm_rename_skips_fresh(monkeypatch, tmp_path: Path) -> None:
    tpath = tmp_path / "a.json"
    tpath.write_text("{}", encoding="utf-8")
    resolved = SimpleNamespace(
        managed_transcript_id="tx-1",
        transcript_path=tpath,
    )
    resolver = MagicMock()
    resolver.list_admitted.return_value = [resolved]
    svc = BulkLlmSuggestionsService(resolver=resolver)
    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm._rename_content_mode",
        lambda: "auto",
    )
    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm.load_transcript_segments",
        lambda _: [{"speaker": "A", "text": "hi"}],
    )
    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm._rename_cache_fresh",
        lambda *a, **k: True,
    )
    suggest = MagicMock()
    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm.suggest_rename_stems",
        suggest,
    )

    result = svc.warm_rename()
    assert result.skipped_fresh_count == 1
    suggest.assert_not_called()


@pytest.mark.unit
def test_warm_isolates_errors_per_transcript(monkeypatch, tmp_path: Path) -> None:
    good = tmp_path / "good.json"
    bad = tmp_path / "bad.json"
    good.write_text("{}", encoding="utf-8")
    bad.write_text("{}", encoding="utf-8")
    resolver = MagicMock()
    resolver.list_admitted.return_value = [
        SimpleNamespace(managed_transcript_id="g", transcript_path=good),
        SimpleNamespace(managed_transcript_id="b", transcript_path=bad),
    ]
    svc = BulkLlmSuggestionsService(resolver=resolver)
    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm._speaker_name_cache_fresh",
        lambda **_: False,
    )

    def _segments(path):
        if "bad" in str(path):
            raise OSError("read fail")
        return [{"speaker": "A", "text": "x"}]

    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm.load_transcript_segments",
        _segments,
    )
    monkeypatch.setattr(
        "transcriptx.services.llm_suggestions.bulk_warm.suggest_speaker_names",
        lambda path, **k: NameSuggestionsResult(
            transcript_path=str(path),
            managed_transcript_id="g",
            transcript_fingerprint="fp",
        ),
    )

    result = svc.warm_speaker_names()
    assert result.ok_count == 1
    assert result.error_count == 1


@pytest.mark.unit
def test_warm_suggestions_cli_requires_kind() -> None:
    from transcriptx.warm_suggestions import main

    assert main([]) == 2


@pytest.mark.unit
def test_warm_suggestions_cli_dry_run(monkeypatch) -> None:
    from transcriptx.app.models.results import WarmSuggestionsResult
    from transcriptx.warm_suggestions import main

    monkeypatch.setattr("transcriptx._bootstrap.bootstrap", lambda: None)
    run = MagicMock(
        return_value=WarmSuggestionsResult(
            success=True,
            ok_count=1,
            log_lines=["a.json [speaker_names]: ok — dry-run"],
        )
    )
    monkeypatch.setattr("transcriptx.warm_suggestions.run_warm_suggestions", run)
    assert main(["--all", "--dry-run"]) == 0
    run.assert_called_once()


@pytest.mark.unit
def test_run_warm_suggestions_workflow_no_kinds() -> None:
    from transcriptx.app.models.requests import WarmSuggestionsRequest
    from transcriptx.app.workflows.warm_suggestions import run_warm_suggestions

    result = run_warm_suggestions(WarmSuggestionsRequest())
    assert not result.success
    assert result.errors
