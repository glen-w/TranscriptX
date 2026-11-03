"""Shell tax contracts — logo cache + per-run CSS inject."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.web.streamlit_doubles import DummyHomeStreamlit


@pytest.mark.unit
def test_inject_global_styles_emits_every_run(monkeypatch) -> None:
    """Streamlit drops elements the latest run did not emit; CSS must be
    re-sent on every script run (1.1.0 regression: unstyled after first nav)."""
    import transcriptx.web.shell as shell

    DummyHomeStreamlit.session_state = {}
    markdown_calls: list[str] = []
    html_calls: list[int] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def markdown(body, *_a, **_k):
            markdown_calls.append(body)

        @staticmethod
        def html(*_a, **_k):
            html_calls.append(1)

    monkeypatch.setattr(shell, "st", _St)

    shell.inject_global_styles()
    shell.inject_global_styles()
    assert len(markdown_calls) == 2
    assert len(html_calls) == 2
    assert all("tx-sidebar-brand" in body for body in markdown_calls)
    # Static module string: no per-run string building.
    assert markdown_calls[0] is shell._GLOBAL_STYLES_CSS


@pytest.mark.unit
def test_render_brand_logo_emits_exactly_one_img(monkeypatch) -> None:
    import transcriptx.web.shell as shell

    bodies: list[str] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def markdown(body, *_a, **_k):
            bodies.append(body)

    monkeypatch.setattr(shell, "st", _St)
    shell.render_brand_logo()
    assert len(bodies) == 1
    html = bodies[0]
    assert html.count("<img") == 1
    assert 'class="tx-logo"' in html
    assert "data-tx-src-light=" in html
    assert "data-tx-src-dark=" in html
    assert "tx-logo-light-chrome" not in html
    assert "tx-logo-dark-chrome" not in html


@pytest.mark.unit
def test_logo_data_uri_is_cached(tmp_path) -> None:
    import transcriptx.web.shell as shell

    logo = tmp_path / "logo.png"
    logo.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 64)
    shell._logo_data_uri.cache_clear()

    uri1 = shell._logo_data_uri(str(logo))
    info = shell._logo_data_uri.cache_info()
    uri2 = shell._logo_data_uri(str(logo))
    info2 = shell._logo_data_uri.cache_info()

    assert uri1 == uri2
    assert uri1.startswith("data:image/png;base64,")
    assert info.hits == 0 and info.misses == 1
    assert info2.hits == 1 and info2.misses == 1
    assert Path(str(logo)).is_file()
