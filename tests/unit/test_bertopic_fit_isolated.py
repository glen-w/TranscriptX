"""Unit tests for subprocess-isolated BERTopic fit helpers (offline, mocked)."""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from transcriptx.core.utils.bertopic_fit import isolated as fi
from transcriptx.core.utils.bertopic_fit.worker import _serialize_probs


@pytest.mark.unit
def test_cfg_snapshot_none_and_partial_attrs() -> None:
    assert fi._cfg_snapshot(None) == {}
    cfg = SimpleNamespace(min_topic_size=12, unrelated=99)
    snap = fi._cfg_snapshot(cfg)
    assert snap["min_topic_size"] == 12
    assert "unrelated" not in snap
    assert "embedding_model" not in snap


@pytest.mark.unit
def test_fit_isolated_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_timeout(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="worker", timeout=1)

    monkeypatch.setattr(fi.subprocess, "run", _raise_timeout)
    out = fi.fit_bertopic_isolated(["a", "b", "c"] * 2, None, timeout_seconds=1)
    assert out.ok is False
    assert out.error == "bertopic_fit_timeout"
    assert out.exit_code is None
    assert out.topic_assignments == []


@pytest.mark.unit
def test_fit_isolated_missing_result_file(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(fi.subprocess, "run", lambda *_a, **_k: _Completed())
    out = fi.fit_bertopic_isolated(["doc"] * 5, None)
    assert out.ok is False
    assert out.error == "bertopic_fit_missing_result"
    assert out.exit_code == 0


@pytest.mark.unit
def test_fit_isolated_soft_fail_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    def _run(cmd, **_kwargs):
        result_path = cmd[-1]
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump({"ok": False, "error": "boom_from_worker"}, fh)

        class _Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Completed()

    monkeypatch.setattr(fi.subprocess, "run", _run)
    out = fi.fit_bertopic_isolated(["doc"] * 5, None)
    assert out.ok is False
    assert out.error == "boom_from_worker"
    assert out.exit_code == 0


@pytest.mark.unit
def test_fit_isolated_success_reads_result(monkeypatch: pytest.MonkeyPatch) -> None:
    def _run(cmd, **_kwargs):
        result_path = cmd[-1]
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "ok": True,
                    "topic_assignments": [0, 1, 0],
                    "topic_probs": [[0.9, 0.1], [0.2, 0.8], [0.7, 0.3]],
                    "topics": [{"topic_id": 0, "label": "alpha"}],
                    "duration_seconds": 0.42,
                },
                fh,
            )

        class _Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Completed()

    monkeypatch.setattr(fi.subprocess, "run", _run)
    cfg = SimpleNamespace(min_topic_size=5, top_n_words=8)
    out = fi.fit_bertopic_isolated(["a", "b", "c"], cfg)
    assert out.ok is True
    assert out.topic_assignments == [0, 1, 0]
    assert out.topics == [{"topic_id": 0, "label": "alpha"}]
    assert out.duration_seconds == pytest.approx(0.42)
    assert out.exit_code == 0
    assert out.error is None


@pytest.mark.unit
def test_fit_isolated_exit_139_includes_signal_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Completed:
        returncode = 139
        stdout = ""
        stderr = "fatal"

    monkeypatch.setattr(fi.subprocess, "run", lambda *_a, **_k: _Completed())
    out = fi.fit_bertopic_isolated(["doc"] * 3, None)
    assert out.ok is False
    assert out.exit_code == 139
    assert out.error is not None
    assert "bertopic_native_crash:exit=139" in out.error
    assert "signal=11" in out.error


@pytest.mark.unit
def test_serialize_probs_none_list_and_non_array() -> None:
    assert _serialize_probs(None) is None
    assert _serialize_probs([[1, 2], None, [3]]) == [[1.0, 2.0], None, [3.0]]
    assert _serialize_probs("not-probs") is None
