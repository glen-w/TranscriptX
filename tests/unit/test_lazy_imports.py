"""Unit tests for transcriptx.core.utils.lazy_imports."""

from __future__ import annotations

import importlib
import types
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.utils import lazy_imports as li


@pytest.mark.unit
def test_lazy_import_caches_module() -> None:
    li._cache.clear()
    first = li.lazy_import("json")
    second = li.lazy_import("json")
    assert first is second
    assert first is importlib.import_module("json")


@pytest.mark.unit
def test_lazy_module_defers_import_until_attribute_access() -> None:
    calls: list[str] = []

    def _fake_optional(module_name: str, purpose: str, extra: str | None = None):
        calls.append(module_name)
        mod = types.ModuleType(module_name)
        mod.dumps = lambda obj: "ok"
        return mod

    with patch.object(li, "optional_import", side_effect=_fake_optional):
        proxy = li.LazyModule("fake.lazy", "testing")
        assert calls == []
        assert proxy.dumps({"a": 1}) == "ok"
        assert calls == ["fake.lazy"]


@pytest.mark.unit
def test_lazy_module_repr() -> None:
    proxy = li.LazyModule("json", "testing")
    assert "LazyModule" in repr(proxy)
    assert "json" in repr(proxy)


@pytest.mark.unit
def test_optional_import_raises_with_install_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    li._cache.clear()
    monkeypatch.delenv("TRANSCRIPTX_CORE", raising=False)
    monkeypatch.delenv("TRANSCRIPTX_NO_AUTO_INSTALL", raising=False)

    with patch.object(li, "lazy_import", side_effect=ImportError("missing")):
        with pytest.raises(ImportError, match="required for plotting"):
            li.optional_import(
                "definitely_missing_lazy_imports_pkg",
                "plotting",
                extra="viz",
                auto_install=False,
            )


@pytest.mark.unit
def test_optional_import_auto_install_requires_extra() -> None:
    li._cache.clear()
    with patch.object(li, "lazy_import", side_effect=ImportError("missing")):
        with pytest.raises(ValueError, match="requires extra="):
            li.optional_import(
                "json",
                "testing",
                auto_install=True,
            )


@pytest.mark.unit
def test_optional_import_core_mode_disables_auto_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    li._cache.clear()
    monkeypatch.setenv("TRANSCRIPTX_CORE", "1")
    with patch.object(li, "lazy_import", side_effect=ImportError("missing")):
        with pytest.raises(ImportError, match="core mode: auto-install disabled"):
            li.optional_import(
                "json",
                "testing",
                extra="viz",
                auto_install=True,
            )


@pytest.mark.unit
def test_try_install_package_returns_true_when_module_already_importable() -> None:
    ok, err = li._try_install_package("json", "json", "stdlib json")
    assert ok is True
    assert err == ""


@pytest.mark.unit
def test_try_install_package_returns_false_on_failed_pip() -> None:
    fake_result = MagicMock(returncode=1, stderr="pip failed", stdout="")

    def _fake_run(cmd, capture_output, text, timeout):
        return fake_result

    with (
        patch(
            "transcriptx.core.utils.lazy_imports.importlib.import_module",
            side_effect=ImportError("nope"),
        ),
        patch(
            "transcriptx.core.utils.lazy_imports.subprocess.run", side_effect=_fake_run
        ),
    ):
        ok, err = li._try_install_package(
            "definitely_missing_pkg_xyz",
            "definitely_missing_pkg_xyz",
            "testing",
        )
    assert ok is False
    assert "pip failed" in err


@pytest.mark.unit
def test_lazy_module_factory() -> None:
    proxy = li.lazy_module("json", "stdlib")
    assert proxy.dumps({"a": 1}) == '{"a": 1}'


@pytest.mark.unit
def test_get_pandas_and_matplotlib_pyplot() -> None:
    pd = li.get_pandas()
    plt = li.get_matplotlib_pyplot()
    assert hasattr(pd, "DataFrame")
    assert hasattr(plt, "figure")


@pytest.mark.unit
def test_core_mode_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_CORE", "true")
    assert li._core_mode() is True
    monkeypatch.delenv("TRANSCRIPTX_CORE", raising=False)
    assert isinstance(li._core_mode(), bool)
