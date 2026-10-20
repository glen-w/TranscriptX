"""Shell tax contracts — logo cache + once-per-session CSS inject."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.web.streamlit_doubles import DummyHomeStreamlit


@pytest.mark.unit
def test_inject_global_styles_once_per_session(monkeypatch) -> None:
    import transcriptx.web.shell as shell

    DummyHomeStreamlit.session_state = {}
    markdown_calls: list[int] = []
    html_calls: list[int] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def markdown(*_a, **_k):
            markdown_calls.append(1)

        @staticmethod
        def html(*_a, **_k):
            html_calls.append(1)

    monkeypatch.setattr(shell, "st", _St)

    shell.inject_global_styles()
    shell.inject_global_styles()
    assert len(markdown_calls) == 1
    assert len(html_calls) == 1

    shell.inject_global_styles(force=True)
    assert len(markdown_calls) == 2
    assert len(html_calls) == 2


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
