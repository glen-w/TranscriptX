"""Patch Streamlit (and other names) on every Insights implementation module."""

from __future__ import annotations

import importlib
from contextlib import ExitStack, contextmanager
from typing import Iterator
from unittest.mock import patch

INSIGHTS_IMPL_MODULES = (
    "transcriptx.web.blocks.implementations.insights",
    "transcriptx.web.blocks.implementations.insights_support",
    "transcriptx.web.blocks.implementations.insights_contract",
    "transcriptx.web.blocks.implementations.insights_highlights",
    "transcriptx.web.blocks.implementations.insights_llm",
    "transcriptx.web.blocks.implementations.insights_markers",
)


def patch_insights_attr(monkeypatch, name: str, value) -> None:
    for modname in INSIGHTS_IMPL_MODULES:
        mod = importlib.import_module(modname)
        if hasattr(mod, name):
            monkeypatch.setattr(mod, name, value)


@contextmanager
def patch_insights_object(name: str, value) -> Iterator[None]:
    with ExitStack() as stack:
        for modname in INSIGHTS_IMPL_MODULES:
            mod = importlib.import_module(modname)
            if hasattr(mod, name):
                stack.enter_context(patch.object(mod, name, value))
        yield
