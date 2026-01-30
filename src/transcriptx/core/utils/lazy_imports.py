"""
Centralized lazy import helpers for optional dependencies.

Use these helpers to avoid importing heavy modules at import time and to
standardize error messages and install guidance for optional features.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Optional

_cache: dict[str, Any] = {}
_locks: dict[str, threading.Lock] = {}


class LazyModule:
    """Proxy that lazily imports a module on first attribute access."""

    def __init__(self, module_name: str, purpose: str, extra: Optional[str] = None):
        self._module_name = module_name
        self._purpose = purpose
        self._extra = extra
        self._module: Optional[Any] = None
        self._lock = threading.Lock()

    def _load(self) -> Any:
        if self._module is not None:
            return self._module
        with self._lock:
            if self._module is None:
                self._module = optional_import(
                    self._module_name, self._purpose, self._extra
                )
        return self._module

    def __getattr__(self, name: str) -> Any:
        return getattr(self._load(), name)

    def __dir__(self) -> list[str]:
        return dir(self._load())

    def __repr__(self) -> str:
        return f"<LazyModule {self._module_name}>"


def _get_lock(module_name: str) -> threading.Lock:
    lock = _locks.get(module_name)
    if lock is None:
        lock = threading.Lock()
        _locks[module_name] = lock
    return lock


def lazy_import(module_name: str) -> Any:
    """Lazy import with thread-safe caching."""
    if module_name in _cache:
        return _cache[module_name]

    lock = _get_lock(module_name)
    with lock:
        if module_name in _cache:
            return _cache[module_name]
        # Use importlib.import_module for reliable submodule imports
        # This properly handles cases like "playwright.sync_api"
        module = importlib.import_module(module_name)
        _cache[module_name] = module
        return module


def _try_install_package(
    package_name: str, module_name: str, purpose: str, extra: Optional[str] = None
) -> bool:
    """
    Attempt to install a package at runtime if import fails.
    
    Args:
        package_name: Name of the package to install (e.g., "convokit")
        module_name: Name of the module to import (e.g., "convokit")
        purpose: Description of what the package is used for
        extra: Optional extra name for pip install transcriptx[extra]
    
    Returns:
        True if installation succeeded and module can now be imported, False otherwise
    """
    try:
        # Try importing first to see if it's already available
        importlib.import_module(module_name)
        return True
    except ImportError:
        pass  # Package not available, will try to install
    
    # Try to install the package
    try:
        install_cmd = [sys.executable, "-m", "pip", "install", package_name]
        result = subprocess.run(
            install_cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            # Verify installation by trying to import
            try:
                importlib.import_module(module_name)
                return True
            except ImportError:
                return False
        return False
    except Exception:
        return False


def optional_import(
    module_name: str, purpose: str, extra: Optional[str] = None, auto_install: bool = False
) -> Any:
    """
    Optional import with a consistent error message and install hint.
    
    Args:
        module_name: Name of the module to import
        purpose: Description of what the module is used for
        extra: Optional extra name for pip install transcriptx[extra]
        auto_install: If True, attempt to install the package if import fails
    
    Returns:
        The imported module
    
    Raises:
        ImportError: If the module cannot be imported (and auto_install is False or fails)
    """
    try:
        return lazy_import(module_name)
    except ImportError as exc:
        # Try auto-installation if enabled
        if auto_install:
            # Use module_name as package_name by default, but handle special cases
            package_name = module_name.split(".")[0]  # e.g., "playwright.sync_api" -> "playwright"
            if _try_install_package(package_name, module_name, purpose, extra):
                # Retry import after installation
                try:
                    return lazy_import(module_name)
                except ImportError:
                    pass  # Fall through to error message
        
        extra_msg = (
            f" Install with: pip install transcriptx[{extra}]" if extra else ""
        )
        raise ImportError(
            f"{module_name} is required for {purpose}.{extra_msg}"
        ) from exc


def lazy_module(module_name: str, purpose: str, extra: Optional[str] = None) -> Any:
    return LazyModule(module_name, purpose, extra)


class LazyPyplot(LazyModule):
    def _load(self) -> Any:
        return get_matplotlib_pyplot()


def lazy_pyplot() -> Any:
    return LazyPyplot("matplotlib.pyplot", "plotting", "visualization")


def get_torch() -> Any:
    return optional_import("torch", "ML models", "emotion")


def get_transformers() -> Any:
    return optional_import("transformers", "transformer models", "emotion")


def get_matplotlib_pyplot() -> Any:
    matplotlib = optional_import("matplotlib", "plotting", "visualization")
    matplotlib.use("Agg")
    # Optional suppression/tuning of matplotlib's "More than 20 figures have been opened"
    # warning. Set env var to an integer (e.g., "0" to disable warnings entirely).
    #
    # Example:
    #   TRANSCRIPTX_MPL_MAX_OPEN_WARNING=0 transcriptx ...
    max_open_warning = os.getenv("TRANSCRIPTX_MPL_MAX_OPEN_WARNING")
    if max_open_warning is not None:
        try:
            matplotlib.rcParams["figure.max_open_warning"] = int(max_open_warning)
        except Exception:
            # If parsing fails or rcParams is unavailable, just ignore and proceed.
            pass
    return optional_import("matplotlib.pyplot", "plotting", "visualization")


def get_matplotlib() -> Any:
    matplotlib = optional_import("matplotlib", "plotting", "visualization")
    matplotlib.use("Agg")
    return matplotlib


def get_seaborn() -> Any:
    return optional_import("seaborn", "plotting", "visualization")


def get_pandas() -> Any:
    return optional_import("pandas", "data processing", "visualization")


def get_wordcloud() -> Any:
    return optional_import("wordcloud", "wordclouds", "visualization")


def get_folium() -> Any:
    return optional_import("folium", "map visualization", "maps")


def get_geopy() -> Any:
    return optional_import("geopy", "geocoding", "maps")


def _check_playwright_browser_installed() -> bool:
    """
    Check if Playwright Chromium browser is installed without installing it.
    
    Returns:
        True if browser is available, False otherwise
    """
    try:
        from playwright.sync_api import sync_playwright
        
        # Lightweight check: try to get browser executable path
        # This doesn't launch a browser, just checks if it's installed
        try:
            with sync_playwright() as p:
                browser_type = p.chromium
                browser_path = browser_type.executable_path
                # Check if the executable path exists
                if browser_path and Path(browser_path).exists():
                    return True
        except Exception:
            # Browser not found or not installed
            pass
        
        return False
    except ImportError:
        # Playwright module itself is not available
        return False


def _ensure_playwright_browser_installed(silent: bool = False) -> bool:
    """
    Ensure Playwright Chromium browser is installed.
    
    This function checks if the Chromium browser is available and installs it
    if needed. It uses a lightweight check before attempting installation.
    
    Args:
        silent: If True, suppress success messages (only show warnings/errors)
    
    Returns:
        True if browser is available (or was successfully installed), False otherwise
    """
    try:
        from playwright.sync_api import sync_playwright
        
        # Check if browser is already installed
        if _check_playwright_browser_installed():
            return True
        
        # Browser not found, try to install it
        try:
            if not silent:
                print("Installing Playwright Chromium browser (this may take a few minutes)...")
            install_cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
            result = subprocess.run(
                install_cmd, 
                capture_output=True, 
                text=True, 
                timeout=600,  # 10 minute timeout
                check=False
            )
            
            if result.returncode == 0:
                if not silent:
                    print("Playwright Chromium browser installed successfully.")
                # Verify installation by checking executable path again
                if _check_playwright_browser_installed():
                    return True
            else:
                stderr_msg = result.stderr.strip() if result.stderr else "Unknown error"
                if not silent:
                    print(f"Warning: Playwright browser installation failed: {stderr_msg}")
        except subprocess.TimeoutExpired:
            if not silent:
                print("Warning: Playwright browser installation timed out.")
        except Exception as e:
            if not silent:
                print(f"Warning: Failed to install Playwright browser: {e}")
        
        return False
    except ImportError:
        # Playwright module itself is not available
        return False


def get_playwright_sync_api(silent: bool = False) -> Any:
    """
    Get the sync_playwright function from playwright.sync_api.
    
    This function:
    1. Lazily imports playwright with auto-installation support
    2. Attempts to ensure Chromium browser is installed at runtime
    3. Returns the sync_playwright function (or None if playwright cannot be imported)
    
    Args:
        silent: If True, suppress installation messages (only show warnings/errors)
    
    Note: Even if browser installation fails, the function is still returned.
    The calling code should handle browser launch failures gracefully.
    
    Returns:
        The sync_playwright function, or None if playwright module is unavailable
    """
    try:
        # Try to import with auto-installation
        sync_api = optional_import("playwright.sync_api", "HTML rendering", "maps", auto_install=True)
        
        # Attempt to ensure browser is installed (non-blocking - will warn if fails)
        _ensure_playwright_browser_installed(silent=silent)
        
        # Return the function - calling code will handle browser launch failures
        return sync_api.sync_playwright
    except ImportError:
        return None


def ensure_playwright_ready(silent: bool = False) -> bool:
    """
    Ensure Playwright package and browser are ready for use.
    
    This function can be called at startup to proactively install Playwright
    if needed, avoiding warnings during analysis.
    
    Args:
        silent: If True, suppress installation messages (only show warnings/errors)
    
    Returns:
        True if Playwright is ready, False otherwise
    """
    try:
        sync_playwright = get_playwright_sync_api(silent=silent)
        if sync_playwright is None:
            return False
        # Verify browser is actually available
        return _check_playwright_browser_installed()
    except Exception:
        return False


def get_convokit() -> Any:
    """Get the convokit module with runtime installation support."""
    return optional_import("convokit", "ConvoKit analysis", "convokit", auto_install=True)

