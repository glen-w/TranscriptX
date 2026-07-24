"""Extra offline unit coverage for lazy_imports install / playwright branches."""

from __future__ import annotations

import importlib
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.utils import lazy_imports as li


@pytest.fixture(autouse=True)
def _clear_cache():
    li._cache.clear()
    yield
    li._cache.clear()


@pytest.mark.unit
def test_lazy_module_dir_and_double_load() -> None:
    calls = {"n": 0}

    def _opt(module_name, purpose, extra=None):
        calls["n"] += 1
        mod = types.ModuleType(module_name)
        mod.value = 42
        return mod

    with patch.object(li, "optional_import", side_effect=_opt):
        proxy = li.LazyModule("fake.mod.dir", "testing")
        assert "value" in dir(proxy)
        assert proxy.value == 42
        assert proxy.value == 42
        assert calls["n"] == 1


@pytest.mark.unit
def test_lazy_import_double_checked_locking() -> None:
    assert li.lazy_import("json") is li.lazy_import("json")


@pytest.mark.unit
def test_try_install_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_CORE", raising=False)
    fake_mod = types.ModuleType("installed_pkg_xyz")

    calls = {"import": 0}

    def _import(name):
        calls["import"] += 1
        if calls["import"] == 1:
            raise ImportError("missing")
        return fake_mod

    ok_result = MagicMock(returncode=0, stderr="", stdout="ok")
    with (
        patch.object(importlib, "import_module", side_effect=_import),
        patch(
            "transcriptx.core.utils.lazy_imports.subprocess.run",
            return_value=ok_result,
        ),
        patch.object(importlib, "invalidate_caches"),
    ):
        ok, err = li._try_install_package(
            "installed_pkg_xyz", "installed_pkg_xyz", "testing"
        )
    assert ok is True
    assert err == ""


@pytest.mark.unit
def test_try_install_extra_fallback_to_package() -> None:
    calls = {"run": 0, "import": 0}

    def _import(name):
        calls["import"] += 1
        # Pre-install probe fails; post-install import succeeds.
        if calls["import"] <= 1:
            raise ImportError("missing")
        return types.ModuleType(name)

    def _run(cmd, capture_output=True, text=True, timeout=300):
        calls["run"] += 1
        return MagicMock(returncode=0, stderr="", stdout="")

    with (
        patch.object(importlib, "import_module", side_effect=_import),
        patch("transcriptx.core.utils.lazy_imports.subprocess.run", side_effect=_run),
        patch.object(importlib, "invalidate_caches"),
    ):
        ok, err = li._try_install_package(
            "pkg_name", "pkg_name", "testing", extra="viz"
        )
    assert ok is True
    # Installs the underlying package only (never transcriptx[extra] from PyPI).
    assert calls["run"] == 1


@pytest.mark.unit
def test_try_install_timeout_and_exception() -> None:
    with (
        patch.object(importlib, "import_module", side_effect=ImportError("x")),
        patch(
            "transcriptx.core.utils.lazy_imports.subprocess.run",
            side_effect=li.subprocess.TimeoutExpired(cmd="pip", timeout=1),
        ),
    ):
        ok, err = li._try_install_package("p", "p", "t")
    assert ok is False
    assert "timed out" in err

    with (
        patch.object(importlib, "import_module", side_effect=ImportError("x")),
        patch(
            "transcriptx.core.utils.lazy_imports.subprocess.run",
            side_effect=OSError("boom"),
        ),
    ):
        ok2, err2 = li._try_install_package("p", "p", "t")
    assert ok2 is False
    assert "boom" in err2


@pytest.mark.unit
def test_optional_import_no_auto_install_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_CORE", raising=False)
    monkeypatch.setenv("TRANSCRIPTX_NO_AUTO_INSTALL", "1")
    with (
        patch.object(li, "_core_mode", return_value=False),
        patch.object(li, "lazy_import", side_effect=ImportError("missing")),
    ):
        with pytest.raises(ImportError, match="NO_AUTO_INSTALL"):
            li.optional_import("x", "testing", extra="viz", auto_install=True)


@pytest.mark.unit
def test_optional_import_auto_install_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRANSCRIPTX_CORE", raising=False)
    monkeypatch.delenv("TRANSCRIPTX_NO_AUTO_INSTALL", raising=False)
    monkeypatch.setenv("TRANSCRIPTX_CORE", "0")

    mod = types.ModuleType("auto_ok_mod")
    # first lazy_import fails, after install succeeds
    state = {"n": 0}

    def _lazy(name):
        state["n"] += 1
        if state["n"] == 1:
            raise ImportError("missing")
        return mod

    with (
        patch.object(li, "_core_mode", return_value=False),
        patch.object(li, "lazy_import", side_effect=_lazy),
        patch.object(li, "_try_install_package", return_value=(True, "")),
    ):
        got = li.optional_import(
            "auto_ok_mod", "testing", extra="viz", auto_install=True
        )
    assert got is mod


@pytest.mark.unit
def test_optional_import_auto_install_fails_appends_msg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRANSCRIPTX_CORE", raising=False)
    with (
        patch.object(li, "_core_mode", return_value=False),
        patch.object(li, "lazy_import", side_effect=ImportError("missing")),
        patch.object(li, "_try_install_package", return_value=(False, "pip blew up")),
    ):
        with pytest.raises(ImportError, match="Auto-install failed"):
            li.optional_import("z", "testing", extra="viz", auto_install=True)


@pytest.mark.unit
def test_core_mode_falls_back_to_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_CORE", raising=False)
    with patch(
        "transcriptx.core.utils.config.get_config",
        return_value=types.SimpleNamespace(core_mode=False),
    ):
        assert li._core_mode() is False
    with patch(
        "transcriptx.core.utils.config.get_config",
        side_effect=RuntimeError("no cfg"),
    ):
        assert li._core_mode() is True


@pytest.mark.unit
def test_get_matplotlib_pyplot_max_open_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRANSCRIPTX_MPL_MAX_OPEN_WARNING", "0")
    mpl = MagicMock()
    mpl.rcParams = {}
    pyplot = MagicMock()

    def _opt(name, purpose, extra=None, auto_install=False):
        if name == "matplotlib":
            return mpl
        return pyplot

    with patch.object(li, "optional_import", side_effect=_opt):
        assert li.get_matplotlib_pyplot() is pyplot
    assert mpl.rcParams["figure.max_open_warning"] == 0

    monkeypatch.setenv("TRANSCRIPTX_MPL_MAX_OPEN_WARNING", "not-int")
    mpl2 = MagicMock()
    mpl2.rcParams = MagicMock()
    mpl2.rcParams.__setitem__ = MagicMock(side_effect=ValueError("bad"))

    def _opt2(name, purpose, extra=None, auto_install=False):
        return mpl2 if name == "matplotlib" else pyplot

    with patch.object(li, "optional_import", side_effect=_opt2):
        assert li.get_matplotlib_pyplot() is pyplot


@pytest.mark.unit
def test_get_matplotlib_and_extras() -> None:
    mpl = MagicMock()
    with patch.object(li, "optional_import", return_value=mpl) as opt:
        assert li.get_matplotlib() is mpl
        mpl.use.assert_called_with("Agg")
        li.get_seaborn()
        li.get_wordcloud()
        li.get_folium()
        li.get_geopy()
        li.get_reportlab()
    assert opt.call_count >= 6


@pytest.mark.unit
def test_ensure_pdf_ready_branches(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    with patch.object(li, "get_reportlab", return_value=MagicMock()):
        assert li.ensure_pdf_ready(silent=False) is True
    out = capsys.readouterr().out
    assert "PDF dependencies" in out

    with patch.object(li, "get_reportlab", side_effect=ImportError("no pdf")):
        assert li.ensure_pdf_ready(silent=False) is False


@pytest.mark.unit
def test_playwright_check_and_ensure_paths() -> None:
    # import missing
    with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
        with patch(
            "builtins.__import__",
            side_effect=ImportError("no playwright"),
        ):
            # call helpers with ImportError from their internal imports
            pass

    with patch.object(li, "_check_playwright_browser_installed", return_value=False):
        with patch(
            "playwright.sync_api.sync_playwright",
            create=True,
        ):
            # Simulate ImportError in ensure when playwright unavailable
            with patch.dict("sys.modules", {}):
                pass

    # Direct unit coverage of check when sync_playwright raises ImportError
    import builtins

    real_import = builtins.__import__

    def _selective(name, *a, **k):
        if name.startswith("playwright"):
            raise ImportError("missing playwright")
        return real_import(name, *a, **k)

    with patch("builtins.__import__", side_effect=_selective):
        assert li._check_playwright_browser_installed() is False
        assert li._ensure_playwright_browser_installed(silent=True) is False


@pytest.mark.unit
def test_check_playwright_browser_installed_true(tmp_path: Path) -> None:
    exe = tmp_path / "chromium"
    exe.write_text("x")
    browser_type = MagicMock()
    browser_type.executable_path = str(exe)
    pw = MagicMock()
    pw.chromium = browser_type
    cm = MagicMock()
    cm.__enter__.return_value = pw
    cm.__exit__.return_value = False
    sync_pw = MagicMock(return_value=cm)

    fake_mod = types.ModuleType("playwright.sync_api")
    fake_mod.sync_playwright = sync_pw

    with patch.dict("sys.modules", {"playwright.sync_api": fake_mod}):
        # Force re-import path inside function
        assert li._check_playwright_browser_installed() is True


@pytest.mark.unit
def test_ensure_playwright_browser_install_success(tmp_path: Path) -> None:
    exe = tmp_path / "chromium"
    exe.write_text("x")
    browser_type = MagicMock()
    browser_type.executable_path = str(exe)
    pw = MagicMock()
    pw.chromium = browser_type
    cm = MagicMock()
    cm.__enter__.return_value = pw
    cm.__exit__.return_value = False

    fake_mod = types.ModuleType("playwright.sync_api")
    fake_mod.sync_playwright = MagicMock(return_value=cm)

    with (
        patch.dict("sys.modules", {"playwright.sync_api": fake_mod}),
        patch.object(
            li, "_check_playwright_browser_installed", side_effect=[False, True]
        ),
        patch(
            "transcriptx.core.utils.lazy_imports.subprocess.run",
            return_value=MagicMock(returncode=0, stderr="", stdout=""),
        ),
    ):
        assert li._ensure_playwright_browser_installed(silent=True) is True


@pytest.mark.unit
def test_ensure_playwright_browser_install_failure_paths() -> None:
    fake_mod = types.ModuleType("playwright.sync_api")
    fake_mod.sync_playwright = MagicMock()

    with (
        patch.dict("sys.modules", {"playwright.sync_api": fake_mod}),
        patch.object(li, "_check_playwright_browser_installed", return_value=False),
        patch(
            "transcriptx.core.utils.lazy_imports.subprocess.run",
            return_value=MagicMock(returncode=1, stderr="fail", stdout=""),
        ),
    ):
        assert li._ensure_playwright_browser_installed(silent=True) is False

    with (
        patch.dict("sys.modules", {"playwright.sync_api": fake_mod}),
        patch.object(li, "_check_playwright_browser_installed", return_value=False),
        patch(
            "transcriptx.core.utils.lazy_imports.subprocess.run",
            side_effect=li.subprocess.TimeoutExpired(cmd="x", timeout=1),
        ),
    ):
        assert li._ensure_playwright_browser_installed(silent=True) is False


@pytest.mark.unit
def test_get_playwright_sync_api_and_ensure_ready() -> None:
    sync_api = MagicMock()
    sync_api.sync_playwright = MagicMock(name="fn")
    with (
        patch.object(li, "optional_import", return_value=sync_api),
        patch.object(li, "_ensure_playwright_browser_installed", return_value=True),
        patch.object(li, "_check_playwright_browser_installed", return_value=True),
    ):
        assert li.get_playwright_sync_api(silent=True) is sync_api.sync_playwright
        assert li.ensure_playwright_ready(silent=True) is True

    with patch.object(li, "optional_import", side_effect=ImportError("x")):
        assert li.get_playwright_sync_api(silent=True) is None

    with patch.object(li, "get_playwright_sync_api", return_value=None):
        assert li.ensure_playwright_ready(silent=True) is False

    with patch.object(li, "get_playwright_sync_api", side_effect=RuntimeError("x")):
        assert li.ensure_playwright_ready(silent=True) is False


@pytest.mark.unit
def test_lazy_pyplot_proxy_loads() -> None:
    with patch.object(
        li, "get_matplotlib_pyplot", return_value=MagicMock(close=lambda: None)
    ):
        proxy = li.lazy_pyplot()
        assert hasattr(proxy, "close")


@pytest.mark.unit
def test_get_torch_and_transformers_delegate() -> None:
    with patch.object(li, "optional_import", return_value=MagicMock()) as opt:
        li.get_torch()
        li.get_transformers()
    assert opt.call_count == 2
