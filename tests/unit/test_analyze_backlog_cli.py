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
        lambda *, require_complete_speakers: [a, b],
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
        lambda *, require_complete_speakers: [path],
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
