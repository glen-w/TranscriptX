from __future__ import annotations

import transcriptx.web.app as app_mod


def test_init_defaults_sets_home_when_page_missing(monkeypatch) -> None:
    state: dict = {}
    monkeypatch.setattr(app_mod.st, "session_state", state)
    app_mod._init_defaults()
    assert state["page"] == "Home"
