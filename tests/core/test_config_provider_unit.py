"""Thread-local config provider."""

from __future__ import annotations

import pytest

import transcriptx.core.utils.config_provider as cp


@pytest.mark.unit
def test_thread_local_provider_set_clear_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cp, "_thread_local_provider", None)
    p = cp.ThreadLocalConfigProvider()

    class Cfg:
        dashboard = object()

    c1 = Cfg()
    c2 = Cfg()

    p.set_config(c1)
    assert p.get_config() is c1
    p.clear_config()
    # Falls back to global after clear
    g = p.get_config()
    assert g is not None

    p.set_config(c2)
    with p.with_config(c1):
        assert p.get_config() is c1
    assert p.get_config() is c2


@pytest.mark.unit
def test_module_level_with_config_restores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "_thread_local_provider", None)

    class Cfg:
        dashboard = object()

    a, b = Cfg(), Cfg()
    cp.set_config(a)
    with cp.with_config(b):
        assert cp.get_config() is b
    assert cp.get_config() is a
    cp.get_config_provider().clear_config()
