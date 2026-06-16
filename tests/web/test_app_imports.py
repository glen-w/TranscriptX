from __future__ import annotations


def test_app_imports_and_navigate_reexport() -> None:
    import transcriptx.web.app as app_mod
    import transcriptx.web.page_modules.transcript as transcript_mod
    import transcriptx.web.router as router_mod
    import transcriptx.web.sidebar as sidebar_mod

    assert app_mod is not None
    assert router_mod is not None
    assert sidebar_mod is not None
    assert app_mod.navigate_to_segment.__name__ == "navigate_to_segment"
    assert transcript_mod.navigate_to_segment.__name__ == "navigate_to_segment"
