from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.pipeline.run_workspace import RunWorkspaceService


def test_create_uses_output_dir_override(tmp_path: Path) -> None:
    service = RunWorkspaceService()
    workspace = service.create(
        transcript_path="/tmp/t.json",
        slug="slug",
        run_id="run1",
        output_dir_override=str(tmp_path / "override"),
    )
    assert workspace.output_dir == str(tmp_path / "override" / "slug" / "run1")
    assert Path(workspace.output_dir).is_dir()


def test_create_prefers_paths_output_dir_over_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = RunWorkspaceService()
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_workspace.paths_module.OUTPUTS_DIR",
        tmp_path / "from_paths",
    )
    monkeypatch.setenv("TRANSCRIPTX_OUTPUT_DIR", str(tmp_path / "from_env"))
    workspace = service.create(
        transcript_path="/tmp/t.json",
        slug="slug",
        run_id="run1",
    )
    assert workspace.output_dir == str(tmp_path / "from_paths" / "slug" / "run1")


def test_create_falls_back_to_env_when_paths_output_dir_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = RunWorkspaceService()
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_workspace.paths_module.OUTPUTS_DIR", ""
    )
    monkeypatch.setenv("TRANSCRIPTX_OUTPUT_DIR", str(tmp_path / "from_env"))
    workspace = service.create(
        transcript_path="/tmp/t.json",
        slug="slug",
        run_id="run1",
    )
    assert workspace.output_dir == str(tmp_path / "from_env" / "slug" / "run1")


def test_create_always_creates_output_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = RunWorkspaceService()
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_workspace.paths_module.OUTPUTS_DIR",
        tmp_path / "created",
    )
    workspace = service.create(transcript_path="/tmp/t.json", slug="s", run_id="r")
    assert Path(workspace.output_dir).exists()


def test_scoped_transcript_output_dir_sets_and_clears_even_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RunWorkspaceService()
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_workspace.set_transcript_output_dir",
        lambda path, out: calls.append(("set", f"{path}|{out}")),
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_workspace.clear_transcript_output_dir",
        lambda path: calls.append(("clear", path)),
    )

    with pytest.raises(RuntimeError, match="boom"):
        with service.scoped_transcript_output_dir("/tmp/t.json", "/tmp/out"):
            raise RuntimeError("boom")

    assert calls[0] == ("set", "/tmp/t.json|/tmp/out")
    assert calls[-1] == ("clear", "/tmp/t.json")
