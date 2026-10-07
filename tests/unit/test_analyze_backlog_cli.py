"""Smoke tests for transcriptx analyze-backlog CLI."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.unit
def test_analyze_backlog_dry_run(monkeypatch, tmp_path: Path, capsys) -> None:
    from transcriptx import analyze_backlog as mod

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text("{}", encoding="utf-8")
    b.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        mod,
        "_discover_backlog",
        lambda *, require_complete_speakers, require_named_speakers=(): [a, b],
    )
    monkeypatch.setattr("transcriptx._bootstrap.bootstrap", lambda: None)
    rc = mod.main(["--dry-run", "--preset", "thorough"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "backlog: 2" in out
    assert "would analyze" in out


@pytest.mark.unit
def test_analyze_backlog_runs_analysis(monkeypatch, tmp_path: Path) -> None:
    from transcriptx import analyze_backlog as mod

    path = tmp_path / "t.json"
    path.write_text("{}", encoding="utf-8")
    called: list = []

    monkeypatch.setattr(
        mod,
        "_discover_backlog",
        lambda *, require_complete_speakers, require_named_speakers=(): [path],
    )
    monkeypatch.setattr("transcriptx._bootstrap.bootstrap", lambda: None)

    def fake_run(request):
        called.append(request)
        return SimpleNamespace(
            success=True,
            status="completed",
            run_dir=tmp_path / "run",
            warnings=[],
            errors=[],
        )

    import transcriptx.app.workflows.analysis as analysis_mod

    monkeypatch.setattr(analysis_mod, "run_analysis", fake_run)
    rc = mod.main(["--preset", "thorough", "--mode", "full", "--max", "1"])
    assert rc == 0
    assert len(called) == 1
    assert called[0].transcript_path == path
    assert called[0].analysis_preset == "thorough"
    assert called[0].mode == "full"


@pytest.mark.unit
def test_has_required_named_speakers_casefold(monkeypatch, tmp_path: Path) -> None:
    from transcriptx import analyze_backlog as mod

    path = tmp_path / "t.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        mod,
        "_effective_named_display_names",
        lambda _p: {"glen", "ana"},
    )
    assert mod._has_required_named_speakers(path, ["Glen"]) is True
    assert mod._has_required_named_speakers(path, ["glen", "Ana"]) is True
    assert mod._has_required_named_speakers(path, ["Glen", "Bob"]) is False


@pytest.mark.unit
def test_discover_backlog_filters_named_speaker(monkeypatch, tmp_path: Path) -> None:
    from transcriptx import analyze_backlog as mod
    from transcriptx.app.models.metadata import TranscriptMetadata

    keep = tmp_path / "with_glen.json"
    skip = tmp_path / "without_glen.json"
    keep.write_text("{}", encoding="utf-8")
    skip.write_text("{}", encoding="utf-8")

    metas = [
        TranscriptMetadata(
            path=keep,
            base_name="with_glen",
            has_analysis_outputs=False,
            speaker_map_status="complete",
        ),
        TranscriptMetadata(
            path=skip,
            base_name="without_glen",
            has_analysis_outputs=False,
            speaker_map_status="complete",
        ),
    ]

    class FakeCtrl:
        def list_transcripts(self):
            return metas

    monkeypatch.setattr(
        "transcriptx.app.controllers.library_controller.LibraryController",
        FakeCtrl,
    )
    monkeypatch.setattr(
        mod,
        "_has_required_named_speakers",
        lambda path, required: path == keep,
    )
    found = mod._discover_backlog(
        require_complete_speakers=True,
        require_named_speakers=["Glen"],
    )
    assert found == [keep]


@pytest.mark.unit
def test_analyze_backlog_passes_require_named_speaker(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from transcriptx import analyze_backlog as mod

    seen: dict = {}

    def fake_discover(*, require_complete_speakers, require_named_speakers=()):
        seen["complete"] = require_complete_speakers
        seen["named"] = list(require_named_speakers)
        return []

    monkeypatch.setattr(mod, "_discover_backlog", fake_discover)
    monkeypatch.setattr("transcriptx._bootstrap.bootstrap", lambda: None)
    rc = mod.main(
        [
            "--dry-run",
            "--require-named-speaker",
            "Glen",
            "--require-complete-speakers",
        ]
    )
    assert rc == 0
    assert seen["complete"] is True
    assert seen["named"] == ["Glen"]
    assert "require_named_speakers=['Glen']" in capsys.readouterr().out
