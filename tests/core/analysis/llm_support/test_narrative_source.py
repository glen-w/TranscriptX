"""Tests for narrative-summary source resolution and serialisation."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.analysis.llm_module_errors import (
    LLM_DEPENDENCY_MISSING,
    ModuleDependencyMissingError,
    ModuleEmptyInputError,
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


def _ctx(tmp_path, stored=None, base: str = "mini"):
    return type(
        "Ctx",
        (),
        {
            "get_analysis_result": lambda self, name: stored,
            "get_base_name": lambda self: base,
            "get_transcript_dir": lambda self: str(tmp_path),
        },
    )()


def _write_summary_artifact(tmp_path, payload, base: str = "mini") -> str:
    summary_dir = tmp_path / "summary" / "data" / "global"
    summary_dir.mkdir(parents=True, exist_ok=True)
    rel = f"summary/data/global/{base}_summary.json"
    (summary_dir / f"{base}_summary.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return rel


@pytest.mark.unit
def test_resolve_summary_payload_corrupt_artifacts_meta_falls_through(
    tmp_path,
) -> None:
    _write_summary_artifact(tmp_path, {"overview": {"paragraph": "on disk"}})
    meta_dir = tmp_path / ".transcriptx"
    meta_dir.mkdir(parents=True)
    (meta_dir / "artifacts_meta.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(ModuleDependencyMissingError):
        resolve_summary_payload(_ctx(tmp_path))


@pytest.mark.unit
def test_resolve_summary_payload_registered_but_empty_signal_raises(tmp_path) -> None:
    rel = _write_summary_artifact(
        tmp_path, {"overview": {}, "key_themes": {"bullets": []}}
    )
    meta_dir = tmp_path / ".transcriptx"
    meta_dir.mkdir(parents=True)
    (meta_dir / "artifacts_meta.json").write_text(
        json.dumps({rel: {"module": "summary"}}), encoding="utf-8"
    )

    with pytest.raises(ModuleEmptyInputError):
        resolve_summary_payload(_ctx(tmp_path))


@pytest.mark.unit
def test_resolve_summary_payload_registered_meta_but_missing_file(tmp_path) -> None:
    rel = "summary/data/global/mini_summary.json"
    meta_dir = tmp_path / ".transcriptx"
    meta_dir.mkdir(parents=True)
    (meta_dir / "artifacts_meta.json").write_text(
        json.dumps({rel: {"module": "summary"}}), encoding="utf-8"
    )

    with pytest.raises(ModuleDependencyMissingError) as exc:
        resolve_summary_payload(_ctx(tmp_path))
    assert exc.value.error_context == {"dependency": "summary", "state": "missing"}


@pytest.mark.unit
def test_resolve_summary_payload_from_manifest_registration(tmp_path) -> None:
    rel = _write_summary_artifact(tmp_path, {"overview": {"paragraph": "manifest"}})
    manifest = {
        "manifest_type": "artifact_manifest",
        "artifacts": [
            {"module": "summary", "rel_path": rel},
            {"module": "stats", "rel_path": "stats/data/x.json"},
            "junk-entry",
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    resolved = resolve_summary_payload(_ctx(tmp_path))
    assert resolved["overview"]["paragraph"] == "manifest"


@pytest.mark.unit
def test_resolve_summary_payload_manifest_without_summary_module(tmp_path) -> None:
    _write_summary_artifact(tmp_path, {"overview": {"paragraph": "unregistered"}})
    manifest = {
        "manifest_type": "artifact_manifest",
        "artifacts": [{"module": "stats", "rel_path": "stats/data/x.json"}],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ModuleDependencyMissingError):
        resolve_summary_payload(_ctx(tmp_path))


@pytest.mark.unit
def test_resolve_summary_payload_invalid_run_results_falls_through(tmp_path) -> None:
    _write_summary_artifact(tmp_path, {"overview": {"paragraph": "x"}})
    (tmp_path / "run_results.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(ModuleDependencyMissingError):
        resolve_summary_payload(_ctx(tmp_path))


@pytest.mark.unit
def test_resolve_summary_payload_from_run_results_projection(tmp_path) -> None:
    _write_summary_artifact(tmp_path, {"overview": {"paragraph": "via run_results"}})
    run_results = {
        "schema_version": 2,
        "run_id": "r1",
        "transcript_key": "mini",
        "modules_enabled": ["summary"],
        "modules_run": ["summary"],
        "modules_skipped": [],
        "modules_failed": [],
        "errors": [],
    }
    (tmp_path / "run_results.json").write_text(
        json.dumps(run_results), encoding="utf-8"
    )

    resolved = resolve_summary_payload(_ctx(tmp_path))
    assert resolved["overview"]["paragraph"] == "via run_results"


@pytest.mark.unit
def test_resolve_summary_payload_run_results_without_summary_run(tmp_path) -> None:
    _write_summary_artifact(tmp_path, {"overview": {"paragraph": "stale"}})
    run_results = {
        "schema_version": 2,
        "run_id": "r1",
        "transcript_key": "mini",
        "modules_enabled": ["summary"],
        "modules_run": [],
        "modules_skipped": [{"module": "summary", "reason": "gated"}],
        "modules_failed": [],
        "errors": [],
    }
    (tmp_path / "run_results.json").write_text(
        json.dumps(run_results), encoding="utf-8"
    )

    with pytest.raises(ModuleDependencyMissingError):
        resolve_summary_payload(_ctx(tmp_path))


@pytest.mark.unit
def test_resolve_summary_payload_stored_payload_with_content(tmp_path) -> None:
    stored = {"status": "success", "payload": {"overview": {"paragraph": "stored"}}}
    resolved = resolve_summary_payload(_ctx(tmp_path, stored=stored))
    assert resolved == {"overview": {"paragraph": "stored"}}


@pytest.mark.unit
def test_resolve_summary_payload_stored_payload_without_signal_raises(
    tmp_path,
) -> None:
    stored = {"status": "success", "payload": {"overview": {}}}
    with pytest.raises(ModuleEmptyInputError):
        resolve_summary_payload(_ctx(tmp_path, stored=stored))


@pytest.mark.unit
@pytest.mark.parametrize("state", ["skipped", "blocked"])
def test_resolve_summary_payload_skipped_or_blocked_dependency(
    tmp_path, state
) -> None:
    with pytest.raises(ModuleDependencyMissingError) as exc:
        resolve_summary_payload(_ctx(tmp_path, stored={"status": state}))
    assert exc.value.error_context == {"dependency": "summary", "state": state}


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
