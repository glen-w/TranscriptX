"""Unit tests for module/pipeline config hashing helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.core.utils import module_hashing as mh


@pytest.mark.unit
def test_hash_payload_is_deterministic_and_key_order_insensitive() -> None:
    a = mh._hash_payload({"b": 2, "a": 1})
    b = mh._hash_payload({"a": 1, "b": 2})
    assert a == b
    assert len(a) == 64


@pytest.mark.unit
def test_compute_module_config_hash_includes_module_name() -> None:
    cfg = {"window": 3}
    h1 = mh.compute_module_config_hash("stats", cfg)
    h2 = mh.compute_module_config_hash("sentiment", cfg)
    assert h1 != h2
    assert mh.compute_module_config_hash("stats", cfg) == h1


@pytest.mark.unit
def test_compute_pipeline_config_hash_changes_with_payload() -> None:
    assert mh.compute_pipeline_config_hash(
        {"mode": "quick"}
    ) != mh.compute_pipeline_config_hash({"mode": "full"})


@pytest.mark.unit
def test_compute_module_source_hash_unknown_module_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.pipeline.module_registry.get_module_function",
        lambda _name: None,
    )
    assert mh.compute_module_source_hash("no_such_module") == ""


@pytest.mark.unit
def test_compute_module_source_hash_reads_source_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import hashlib

    source = tmp_path / "mod.py"
    source.write_text("def run():\n    return 1\n", encoding="utf-8")

    monkeypatch.setattr(
        "transcriptx.core.pipeline.module_registry.get_module_function",
        lambda _name: SimpleNamespace(),
    )
    monkeypatch.setattr(mh.inspect, "getsourcefile", lambda _fn: str(source))
    digest = mh.compute_module_source_hash("stats")
    assert digest == hashlib.sha256(source.read_bytes()).hexdigest()


@pytest.mark.unit
def test_compute_module_source_hash_missing_sourcefile_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.pipeline.module_registry.get_module_function",
        lambda _name: SimpleNamespace(),
    )
    monkeypatch.setattr(mh.inspect, "getsourcefile", lambda _fn: None)
    assert mh.compute_module_source_hash("stats") == ""


@pytest.mark.unit
def test_compute_module_source_hash_exception_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.pipeline.module_registry.get_module_function",
        lambda _name: SimpleNamespace(),
    )

    def _boom(_fn):
        raise OSError("no source")

    monkeypatch.setattr(mh.inspect, "getsourcefile", _boom)
    assert mh.compute_module_source_hash("stats") == ""
