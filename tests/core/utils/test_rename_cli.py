"""CLI rename prompt behavior (prefill + shared validator)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


def test_prompt_for_rename_uses_prefill_when_enabled(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.core.utils.rename import cli as rename_cli

    transcript = tmp_path / "meet.json"
    transcript.write_text("{}")

    monkeypatch.setattr(rename_cli, "_prefill_enabled", lambda: True)
    monkeypatch.setattr(
        rename_cli,
        "rename_managed_transcript",
        lambda *a, **k: MagicMock(
            ok=True,
            transaction_committed=True,
            status=MagicMock(value="committed_complete"),
            operation_id=None,
            message="ok",
        ),
    )

    asked = {}

    class _Q:
        @staticmethod
        def text(msg, **kwargs):
            asked["kwargs"] = kwargs
            m = MagicMock()
            m.ask.return_value = "new_meet"
            return m

    monkeypatch.setitem(__import__("sys").modules, "questionary", _Q)
    monkeypatch.setattr("rich.console.Console.print", lambda *a, **k: None)

    result = rename_cli.prompt_for_rename(str(transcript), "250101_")
    assert result == "new_meet"
    assert asked["kwargs"].get("default") == "250101_"


def test_prompt_for_rename_skips_prefill_when_disabled(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.core.utils.rename import cli as rename_cli

    transcript = tmp_path / "meet.json"
    transcript.write_text("{}")
    monkeypatch.setattr(rename_cli, "_prefill_enabled", lambda: False)
    monkeypatch.setattr(
        rename_cli,
        "rename_managed_transcript",
        lambda *a, **k: MagicMock(
            ok=True,
            transaction_committed=True,
            status=MagicMock(value="committed_complete"),
            operation_id=None,
            message="ok",
        ),
    )
    asked = {}

    class _Q:
        @staticmethod
        def text(msg, **kwargs):
            asked["kwargs"] = kwargs
            m = MagicMock()
            m.ask.return_value = "new_meet"
            return m

    monkeypatch.setitem(__import__("sys").modules, "questionary", _Q)
    monkeypatch.setattr("rich.console.Console.print", lambda *a, **k: None)

    rename_cli.prompt_for_rename(str(transcript), "250101_")
    assert "default" not in asked["kwargs"]


def test_prompt_for_rename_rejects_invalid(monkeypatch, tmp_path: Path) -> None:
    from transcriptx.core.utils.rename import cli as rename_cli

    transcript = tmp_path / "meet.json"
    transcript.write_text("{}")
    monkeypatch.setattr(rename_cli, "_prefill_enabled", lambda: False)

    class _Q:
        @staticmethod
        def text(msg, **kwargs):
            m = MagicMock()
            m.ask.return_value = "bad/name"
            return m

    monkeypatch.setitem(__import__("sys").modules, "questionary", _Q)
    monkeypatch.setattr("rich.console.Console.print", lambda *a, **k: None)
    assert rename_cli.prompt_for_rename(str(transcript), "") is None
