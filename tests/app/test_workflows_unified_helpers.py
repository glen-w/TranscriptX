from __future__ import annotations

from pathlib import Path

from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows import analysis


def test_resolve_modules_uses_defaults_for_empty_and_all(monkeypatch) -> None:
    monkeypatch.setattr(analysis, "get_available_modules", lambda: ["stats", "qa"])
    monkeypatch.setattr(
        analysis,
        "get_default_modules",
        lambda paths, **_kwargs: [f"default:{len(paths)}"],
    )

    assert analysis._resolve_modules(None, ["a.json"]) == (["default:1"], None)
    assert analysis._resolve_modules([], ["a.json", "b.json"]) == (
        ["default:2"],
        None,
    )
    assert analysis._resolve_modules(["all"], ["a.json"]) == (["default:1"], None)


def test_resolve_modules_reports_invalid_modules(monkeypatch) -> None:
    monkeypatch.setattr(analysis, "get_available_modules", lambda: ["stats"])
    monkeypatch.setattr(
        analysis, "get_default_modules", lambda _paths, **_kwargs: ["stats"]
    )

    selected, error = analysis._resolve_modules(["stats", "missing"], ["a.json"])

    assert selected == []
    assert error == "Invalid modules: missing"


def test_resolve_modules_rejects_unsupported_for_group(monkeypatch) -> None:
    monkeypatch.setattr(
        analysis, "get_available_modules", lambda: ["stats", "voice_contours"]
    )
    monkeypatch.setattr(
        analysis, "get_default_modules", lambda _paths, **_kwargs: ["stats"]
    )
    fake_info = type("Info", (), {"supports_group": False})()
    monkeypatch.setattr(
        analysis,
        "get_module_info",
        lambda name: (
            fake_info
            if name == "voice_contours"
            else type("Info", (), {"supports_group": True})()
        ),
    )

    selected, error = analysis._resolve_modules(
        ["stats", "voice_contours"], ["a.json"], for_group=True
    )

    assert selected == []
    assert error is not None
    assert "voice_contours" in error
    assert analysis._resolve_modules(["stats"], ["a.json"], for_group=True) == (
        ["stats"],
        None,
    )


def test_validate_or_fail_outcome_contract() -> None:
    request = AnalysisRequest(transcript_path=Path("missing.json"))
    snapshot: dict = {}

    failed = analysis._validate_or_fail(
        snapshot,
        request,
        lambda _request: ["boom"],
    )
    passed = analysis._validate_or_fail(
        None,
        request,
        lambda _request: [],
    )

    assert failed.valid is False
    assert failed.result is not None
    assert failed.result.errors == ["boom"]
    assert snapshot["status"] == "failed"
    assert snapshot["latest_event"] == "Validation failed"
    assert passed.valid is True
    assert passed.result is None


def test_update_snapshot_noop_when_none() -> None:
    analysis._update_snapshot(None, status="running")


def test_update_snapshot_mutates_in_place() -> None:
    snapshot = {"existing": True}

    analysis._update_snapshot(snapshot, status="running", phase="validating")

    assert snapshot == {
        "existing": True,
        "status": "running",
        "phase": "validating",
    }
