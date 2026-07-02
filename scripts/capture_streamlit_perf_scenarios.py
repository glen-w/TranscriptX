#!/usr/bin/env python3
"""Capture Streamlit perf JSONL scenarios for regression checks."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PERF_DIR = REPO_ROOT / "data" / "perf"

SCENARIOS: list[tuple[str, dict[str, object]]] = [
    (
        "first_browser_load_after_cold_start",
        {"page": "Home", "tx_nav_exp_view": False},
    ),
    (
        "warm_refresh_within_cache_ttl",
        {"page": "Home", "tx_nav_exp_view": False, "_repeat": 2},
    ),
    (
        "refresh_after_cache_ttl_expires",
        {"page": "Home", "tx_nav_exp_view": False, "_clear_cache": True},
    ),
    (
        "widget_triggered_rerun",
        {"page": "Home", "tx_nav_exp_view": True},
    ),
    (
        "navigation_rerun_library",
        {"page": "Library", "tx_nav_exp_view": False},
    ),
]


class _DummySidebar:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _CaptureStreamlit:
    def __init__(self, session_state: dict[str, object]) -> None:
        self.session_state = session_state
        self.query_params: dict[str, str] = {}
        self.sidebar = _DummySidebar()

    @staticmethod
    def error(*_args, **_kwargs):
        return None

    @staticmethod
    def exception(*_args, **_kwargs):
        return None

    @staticmethod
    def rerun():
        return None


@contextmanager
def _perf_output(path: Path):
    os.environ["TRANSCRIPTX_STREAMLIT_PERF"] = "1"
    os.environ["TRANSCRIPTX_STREAMLIT_PERF_PATH"] = str(path)
    from transcriptx.web.perf import reset_output

    reset_output()
    try:
        yield
    finally:
        os.environ.pop("TRANSCRIPTX_STREAMLIT_PERF_PATH", None)


def capture_scenarios() -> int:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    os.environ.setdefault("TRANSCRIPTX_DATA_DIR", str(REPO_ROOT / "data"))

    import streamlit as st
    import transcriptx.web.app as app_mod

    PERF_DIR.mkdir(parents=True, exist_ok=True)
    aggregate_path = PERF_DIR / "streamlit_load_profile.jsonl"
    if aggregate_path.exists():
        aggregate_path.unlink()

    original_render_sidebar = app_mod.render_sidebar
    app_mod.render_sidebar = lambda **_kwargs: None  # type: ignore[method-assign]

    exit_code = 0
    try:
        for scenario_name, seed in SCENARIOS:
            out_path = PERF_DIR / f"{scenario_name}.jsonl"
            session = {k: v for k, v in seed.items() if not str(k).startswith("_")}
            st_obj = _CaptureStreamlit(session)
            repeats = int(seed.get("_repeat", 1))
            with _perf_output(out_path):
                app_mod.st = st_obj  # type: ignore[assignment]
                try:
                    if seed.get("_clear_cache"):
                        st.cache_data.clear()
                    for _ in range(repeats):
                        st_obj.query_params = {"perf_scenario": scenario_name}
                        app_mod.main()
                except Exception as exc:
                    print(f"scenario {scenario_name} failed: {exc}", file=sys.stderr)
                    exit_code = 1

            if out_path.exists():
                with aggregate_path.open("a", encoding="utf-8") as agg:
                    agg.write(out_path.read_text(encoding="utf-8"))
    finally:
        app_mod.render_sidebar = original_render_sidebar  # type: ignore[method-assign]

    return exit_code


def main() -> None:
    raise SystemExit(capture_scenarios())


if __name__ == "__main__":
    main()
