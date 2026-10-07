"""Console script dispatches host subcommands."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.unit
def test_cli_dispatches_warm_suggestions(monkeypatch) -> None:
    from transcriptx.cli import _dispatch_cli

    called: list[list[str]] = []

    def fake_main(argv):
        called.append(list(argv))
        return 0

    monkeypatch.setattr("transcriptx.warm_suggestions.main", fake_main)
    assert _dispatch_cli(["warm-suggestions", "--all"]) == 0
    assert called == [["--all"]]


@pytest.mark.unit
def test_cli_dispatches_identify_speakers(monkeypatch) -> None:
    import sys
    from types import ModuleType

    from transcriptx.cli import _dispatch_cli

    called: list[list[str]] = []
    fake = ModuleType("transcriptx.identify_speakers")

    def fake_main(argv):
        called.append(list(argv))
        return 0

    fake.main = fake_main
    monkeypatch.setitem(sys.modules, "transcriptx.identify_speakers", fake)
    assert _dispatch_cli(["identify-speakers", "--dry-run"]) == 0
    assert called == [["--dry-run"]]


@pytest.mark.unit
@pytest.mark.parametrize(
    "command,module",
    [
        ("import", "transcriptx.import_transcript"),
        ("admit-originals", "transcriptx.admit_originals"),
        ("analyze", "transcriptx.analyze"),
        ("rename", "transcriptx.rename_managed"),
        ("backup", "transcriptx.backup"),
    ],
)
def test_cli_dispatches_allowlisted_commands(
    monkeypatch, command: str, module: str
) -> None:
    import sys
    from types import ModuleType

    from transcriptx.cli import _dispatch_cli

    called: list[list[str]] = []
    fake = ModuleType(module)

    def fake_main(argv):
        called.append(list(argv))
        return 0

    fake.main = fake_main
    monkeypatch.setitem(sys.modules, module, fake)
    assert _dispatch_cli([command, "--flag"]) == 0
    assert called == [["--flag"]]


@pytest.mark.unit
def test_cli_help_lists_host_commands_and_does_not_launch_web(capsys, monkeypatch) -> None:
    import sys

    from transcriptx.cli import main

    monkeypatch.setattr(sys, "argv", ["transcriptx", "--help"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for name in (
        "import",
        "admit-originals",
        "analyze",
        "rename",
        "backup",
        "warm-suggestions",
        "identify-speakers",
    ):
        assert name in out
    assert "Corrections" in out or "GUI" in out


@pytest.mark.unit
def test_cli_returns_none_for_web_args() -> None:
    from transcriptx.cli import _dispatch_cli

    assert _dispatch_cli(["--host", "0.0.0.0"]) is None
    assert _dispatch_cli([]) is None


@pytest.mark.unit
def test_import_transcript_cli_calls_workflow(monkeypatch, tmp_path: Path) -> None:
    from transcriptx import import_transcript as mod
    import transcriptx.io.managed_import_workflow as miw

    src = tmp_path / "raw.json"
    src.write_text("{}", encoding="utf-8")
    called: list[tuple] = []

    monkeypatch.setattr(
        mod,
        "parse_args",
        lambda argv=None: SimpleNamespace(paths=[src], overwrite=False),
    )
    monkeypatch.setattr("transcriptx._bootstrap.bootstrap", lambda: None)

    def fake_import(path, *, overwrite=False, **_kwargs):
        called.append((Path(path), overwrite))
        return SimpleNamespace(json_path=tmp_path / "out.json", speaker_map_error=None)

    monkeypatch.setattr(miw, "run_managed_import_workflow", fake_import)

    assert mod.main([]) == 0
    assert called == [(src, False)]


@pytest.mark.unit
def test_analyze_cli_calls_run_analysis(monkeypatch, tmp_path: Path) -> None:
    from transcriptx import analyze as mod

    path = tmp_path / "t.json"
    path.write_text("{}", encoding="utf-8")
    captured: list = []

    monkeypatch.setattr(mod, "parse_args", lambda argv=None: SimpleNamespace(
        path=path,
        mode="quick",
        analysis_preset="balanced",
        modules="stats",
        allow_unnamed_speakers=True,
        include_unidentified_speakers=False,
    ))
    monkeypatch.setattr("transcriptx._bootstrap.bootstrap", lambda: None)

    def fake_run(request):
        captured.append(request)
        return SimpleNamespace(
            success=True,
            status="completed",
            run_dir=tmp_path / "run",
            modules_executed=["stats"],
            warnings=[],
            errors=[],
        )

    import transcriptx.app.workflows.analysis as analysis_mod

    monkeypatch.setattr(analysis_mod, "run_analysis", fake_run)
    assert mod.main([]) == 0
    assert len(captured) == 1
    assert captured[0].transcript_path == path
    assert captured[0].modules == ["stats"]
    assert captured[0].analysis_preset == "balanced"


@pytest.mark.unit
def test_rename_managed_cli_calls_pipeline(monkeypatch, tmp_path: Path) -> None:
    from transcriptx import rename_managed as mod
    from transcriptx.core.utils.rename.outcome import RenameStatus

    path = tmp_path / "old.json"
    path.write_text("{}", encoding="utf-8")
    called: list[tuple] = []

    monkeypatch.setattr(mod, "parse_args", lambda argv=None: SimpleNamespace(
        path=path, stem="new_name", dry_run=True
    ))
    monkeypatch.setattr("transcriptx._bootstrap.bootstrap", lambda: None)

    def fake_rename(transcript_path, stem, *, dry_run=False):
        called.append((Path(transcript_path), stem, dry_run))
        return SimpleNamespace(
            ok=True,
            partial_success_after_transaction=False,
            message="dry run",
            new_transcript_path=str(tmp_path / "new_name.json"),
            status=RenameStatus.dry_run,
            warnings=[],
            errors=[],
        )

    import transcriptx.core.utils.rename.pipeline as pipeline

    monkeypatch.setattr(pipeline, "rename_managed_transcript", fake_rename)
    assert mod.main([]) == 0
    assert called == [(path, "new_name", True)]


@pytest.mark.unit
def test_backup_cli_create_parses(monkeypatch, tmp_path: Path) -> None:
    from transcriptx import backup as mod

    class FakeService:
        def create_backup(self, paths, dest, options, *, force=False):
            return SimpleNamespace(
                archive_path=dest,
                manifest={"counts": {"transcripts": 1, "files": 2, "uncompressed_bytes": 3}},
            )

    monkeypatch.setattr(mod, "get_default_paths", lambda: object())
    monkeypatch.setattr(mod, "default_backup_dest", lambda paths: tmp_path / "ws.zip")
    monkeypatch.setattr(mod, "WorkspaceBackupService", FakeService)
    assert mod.main(["create"]) == 0
