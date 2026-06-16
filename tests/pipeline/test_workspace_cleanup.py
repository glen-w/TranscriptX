from __future__ import annotations

from transcriptx.core.pipeline.run_workspace import RunWorkspaceService


def test_scoped_transcript_output_dir_always_clears_on_exception(monkeypatch, tmp_path):
    service = RunWorkspaceService()
    calls = {"set": 0, "clear": 0}

    def _fake_set(_transcript_path, _output_dir):
        calls["set"] += 1

    def _fake_clear(_transcript_path):
        calls["clear"] += 1

    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_workspace.set_transcript_output_dir", _fake_set
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_workspace.clear_transcript_output_dir",
        _fake_clear,
    )

    try:
        with service.scoped_transcript_output_dir("t.json", str(tmp_path / "out")):
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert calls["set"] == 1
    assert calls["clear"] == 1
