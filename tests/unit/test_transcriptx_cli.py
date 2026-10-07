"""Console script dispatches host subcommands."""

from __future__ import annotations

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
def test_cli_returns_none_for_web_args() -> None:
    from transcriptx.cli import _dispatch_cli

    assert _dispatch_cli(["--host", "0.0.0.0"]) is None
    assert _dispatch_cli([]) is None
