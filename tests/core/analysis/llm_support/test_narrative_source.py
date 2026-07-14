"""Tests for narrative-summary source resolution and serialisation."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.analysis.llm_module_errors import (
    LLM_DEPENDENCY_MISSING,
    ModuleDependencyMissingError,
)
from transcriptx.core.analysis.llm_support.hashing import sha256_text
from transcriptx.core.analysis.llm_support.narrative_source import (
    resolve_summary_payload,
    serialise_summary_input,
    summary_has_content,
)


@pytest.mark.unit
def test_summary_has_content_false_on_empty() -> None:
    assert summary_has_content({}) is False
    assert summary_has_content({"overview": {}, "key_themes": {"bullets": []}}) is False


@pytest.mark.unit
def test_summary_has_content_true_with_overview() -> None:
    payload = {"overview": {"paragraph": "Something happened"}}
    assert summary_has_content(payload) is True


@pytest.mark.unit
def test_serialise_summary_input_golden() -> None:
    payload = {
        "overview": {"paragraph": "P"},
        "key_themes": {"bullets": ["t1"]},
        "tension_points": {"bullets": []},
        "commitments": {"items": []},
        "ignored": True,
    }
    serialised = serialise_summary_input(payload)
    assert serialised == (
        '{"commitments":{"items":[]},"key_themes":{"bullets":["t1"]},'
        '"overview":{"paragraph":"P"},"tension_points":{"bullets":[]}}'
    )
    assert (
        sha256_text(serialised)
        == "2f27517294ae1b08a3979237e0e0f1677f93f92c7f83c161249072a754981b38"
    )


@pytest.mark.unit
def test_resolve_summary_payload_from_registered_artifact_meta(tmp_path) -> None:
    summary_dir = tmp_path / "summary" / "data" / "global"
    summary_dir.mkdir(parents=True)
    payload = {"overview": {"paragraph": "from disk"}}
    rel = "summary/data/global/mini_summary.json"
    (summary_dir / "mini_summary.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    meta_dir = tmp_path / ".transcriptx"
    meta_dir.mkdir(parents=True)
    (meta_dir / "artifacts_meta.json").write_text(
        json.dumps({rel: {"module": "summary"}}),
        encoding="utf-8",
    )

    context = type(
        "Ctx",
        (),
        {
            "get_analysis_result": lambda self, name: None,
            "get_base_name": lambda self: "mini",
            "get_transcript_dir": lambda self: str(tmp_path),
        },
    )()

    resolved = resolve_summary_payload(context)
    assert resolved["overview"]["paragraph"] == "from disk"


@pytest.mark.unit
def test_resolve_summary_payload_rejects_unregistered_disk_file(tmp_path) -> None:
    summary_dir = tmp_path / "summary" / "data" / "global"
    summary_dir.mkdir(parents=True)
    (summary_dir / "mini_summary.json").write_text(
        json.dumps({"overview": {"paragraph": "stale"}}),
        encoding="utf-8",
    )

    context = type(
        "Ctx",
        (),
        {
            "get_analysis_result": lambda self, name: None,
            "get_base_name": lambda self: "mini",
            "get_transcript_dir": lambda self: str(tmp_path),
        },
    )()
    with pytest.raises(ModuleDependencyMissingError):
        resolve_summary_payload(context)


@pytest.mark.unit
def test_resolve_summary_payload_failed_summary_in_context() -> None:
    context = type(
        "Ctx",
        (),
        {
            "get_analysis_result": lambda self, name: {"status": "error"},
            "get_base_name": lambda self: "mini",
            "get_transcript_dir": lambda self: "/missing",
        },
    )()
    with pytest.raises(ModuleDependencyMissingError) as exc:
        resolve_summary_payload(context)
    assert exc.value.error_code == LLM_DEPENDENCY_MISSING
    assert exc.value.error_context == {"dependency": "summary", "state": "failed"}
