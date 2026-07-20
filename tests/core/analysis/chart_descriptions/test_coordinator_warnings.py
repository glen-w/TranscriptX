"""Coordinator returns only newly appended finalization warnings."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.unit
def test_coordinator_returns_only_new_warnings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from transcriptx.core.analysis.chart_descriptions import coordinator as coord

    incoming = [
        {
            "code": "AGG_WARN",
            "aggregation_key": "x",
            "message": "pre-existing",
        }
    ]

    def fake_write_output_manifest(*_args, **_kwargs):
        return tmp_path / "manifest.json"

    monkeypatch.setattr(coord, "write_output_manifest", fake_write_output_manifest)
    monkeypatch.setattr(coord, "_chart_descriptions_selected", lambda _mods: False)

    result = coord.run_finalization_coordinator(
        run_dir=tmp_path,
        run_id="run-1",
        transcript_key="tx",
        selected_modules=["stats"],
        modules_enabled=["stats"],
        config=SimpleNamespace(llm=SimpleNamespace(enabled=False, provider="null")),
        run_kind="transcript",
        run_group_synthesis=False,
        aggregation_warnings=incoming,
        already_holding_lock=True,
    )

    assert result.warnings == []
    assert incoming == [
        {
            "code": "AGG_WARN",
            "aggregation_key": "x",
            "message": "pre-existing",
        }
    ]
