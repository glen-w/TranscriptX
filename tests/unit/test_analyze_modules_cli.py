"""Smoke tests for transcriptx analyze-modules CLI."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.unit
def test_missing_modules_reads_newest_run(tmp_path: Path, monkeypatch) -> None:
    from transcriptx import analyze_modules as mod

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    out_root = tmp_path / "out"
    run = out_root / "20260101_000000_abc"
    run.mkdir(parents=True)
    (run / "run_results.json").write_text(
        json.dumps({"modules_run": ["transcript_output"]}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "transcriptx.core.utils._path_core.get_transcript_dir",
        lambda _p: str(out_root),
    )
    monkeypatch.setattr(mod, "_newest_run_dir", lambda _root: run)

    assert mod._missing_modules(transcript, ["transcript_output", "llm_summary"]) == [
        "llm_summary"
    ]
    assert mod._missing_modules(transcript, ["transcript_output"]) == []


@pytest.mark.unit
def test_discover_targets_skips_complete(monkeypatch, tmp_path: Path) -> None:
    from transcriptx import analyze_modules as mod

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text("{}", encoding="utf-8")
    b.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "transcriptx.core.utils.file_discovery.discover_managed_transcript_paths",
        lambda: [a, b],
    )
    monkeypatch.setattr(
        mod,
        "_missing_modules",
        lambda path, required: [] if path == a else list(required),
    )
    targets = mod._discover_targets(
        modules=["transcript_output", "llm_summary"],
        force=False,
    )
    assert targets == [(b, ["transcript_output", "llm_summary"])]


@pytest.mark.unit
def test_analyze_modules_dry_run(monkeypatch, tmp_path: Path, capsys) -> None:
    from transcriptx import analyze_modules as mod

    path = tmp_path / "t.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        mod,
        "_discover_targets",
        lambda *, modules, force: [(path, list(modules))],
    )
    monkeypatch.setattr("transcriptx._bootstrap.bootstrap", lambda: None)
    rc = mod.main(["--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "module-backlog: 1" in out
    assert "transcript_output" in out
    assert "llm_summary" in out


@pytest.mark.unit
def test_analyze_modules_runs_analysis(monkeypatch, tmp_path: Path) -> None:
    from transcriptx import analyze_modules as mod

    path = tmp_path / "t.json"
    path.write_text("{}", encoding="utf-8")
    called: list = []

    monkeypatch.setattr(
        mod,
        "_discover_targets",
        lambda *, modules, force: [(path, ["transcript_output", "llm_summary"])],
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
    rc = mod.main(["--max", "1"])
    assert rc == 0
    assert len(called) == 1
    assert called[0].modules == ["transcript_output", "llm_summary"]
    assert called[0].allow_unnamed_speakers is True
