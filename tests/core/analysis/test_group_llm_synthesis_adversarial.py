"""Adversarial / durability tests for group LLM synthesis."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


from transcriptx.core.analysis.group_llm_synthesis import errors as err
from transcriptx.core.analysis.group_llm_synthesis.digests import compute_input_digests
from transcriptx.core.analysis.group_llm_synthesis.finalize_hook import (
    run_synthesis_publish_and_manifest,
)
from transcriptx.core.analysis.group_llm_synthesis.generation import (
    gc_old_committed_generations,
    gc_uncommitted_generations,
    read_active,
    write_active,
    write_commit,
)
from transcriptx.core.analysis.group_llm_synthesis.lock import (
    SynthesisLockTimeout,
    synthesis_lock,
)
from transcriptx.core.analysis.group_llm_synthesis.paths import (
    generation_dir,
    generations_dir,
    global_summary_rel,
    lock_path,
    synthesis_root,
)
from transcriptx.core.analysis.group_llm_synthesis.resolve import (
    ResolverCache,
    load_group_llm_summary,
)
from transcriptx.core.analysis.group_llm_synthesis.schemas import (
    LOCK_FILENAME,
    SCHEMA_GLOBAL,
)
from transcriptx.core.analysis.group_llm_synthesis.synthesize import (
    run_group_llm_synthesis,
)
from transcriptx.core.pipeline.manifest_builder import write_output_manifest


def _write_collect(run: Path) -> Path:
    collect = run / "llm_summary"
    collect.mkdir(parents=True, exist_ok=True)
    blob = collect / "llm_summary.json"
    blob.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "aggregation_key": "llm_summary",
                "summaries": [
                    {
                        "summary": "Session A",
                        "source_transcript_id": "t1",
                        "order_index": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (run / "group_run_metadata.json").write_text("{}", encoding="utf-8")
    return blob


def _cfg(*, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        analysis=SimpleNamespace(
            group_llm_synthesis=SimpleNamespace(enabled=enabled, effort="low")
        ),
        llm=SimpleNamespace(
            enabled=True,
            provider="ollama",
            model="test",
            base_url="http://localhost:11434",
            seed=0,
            availability_timeout=1.0,
        ),
    )


def _mock_runtime():
    return SimpleNamespace(
        effort="low",
        model="test",
        max_input_chars=50_000,
        request_timeout=30.0,
        max_output_tokens=512,
    )


def _publish_success(run: Path) -> str:
    mock_client = MagicMock()
    mock_client.generate.return_value = json.dumps({"summary": "Rollup OK"})
    with synthesis_lock(run):
        with (
            patch(
                "transcriptx.core.analysis.group_llm_synthesis.synthesize.build_ollama_analysis_client",
                return_value=mock_client,
            ),
            patch(
                "transcriptx.core.analysis.group_llm_synthesis.synthesize.require_ollama_analysis",
            ),
            patch(
                "transcriptx.core.analysis.group_llm_synthesis.synthesize.resolve_llm_runtime",
                return_value=_mock_runtime(),
            ),
        ):
            result = run_group_llm_synthesis(
                run_root=run,
                run_id="g1",
                config=_cfg(),
                want_global=True,
                want_speakers=False,
            )
    assert result.published
    assert result.generation_id
    return result.generation_id


def test_unexpected_error_attempt_not_cancelled(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    _write_collect(run)
    with synthesis_lock(run):
        with patch(
            "transcriptx.core.analysis.group_llm_synthesis.synthesize.require_ollama_analysis",
            side_effect=RuntimeError("boom"),
        ):
            # require_ollama raises LLMConfigurationError normally; force unexpected
            # after gate by patching resolve to raise after require succeeds
            pass
        with (
            patch(
                "transcriptx.core.analysis.group_llm_synthesis.synthesize.require_ollama_analysis",
            ),
            patch(
                "transcriptx.core.analysis.group_llm_synthesis.synthesize.resolve_llm_runtime",
                return_value=_mock_runtime(),
            ),
            patch(
                "transcriptx.core.analysis.group_llm_synthesis.synthesize.build_ollama_analysis_client",
                side_effect=RuntimeError("client boom"),
            ),
        ):
            result = run_group_llm_synthesis(
                run_root=run,
                run_id="g1",
                config=_cfg(),
                want_global=True,
                want_speakers=False,
            )
    assert result.published is False
    assert result.attempt_status == "failed"
    assert result.error_code == err.UNEXPECTED_ERROR
    assert read_active(run) is None or "cancelled" not in str(
        (read_active(run) or {}).get("overall_status")
    )


def test_manifest_fail_retains_prior_generation(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    _write_collect(run)
    first = _publish_success(run)
    first_dir = generations_dir(run) / first
    assert first_dir.is_dir()

    warnings: list = []
    with synthesis_lock(run):
        with patch(
            "transcriptx.core.analysis.group_llm_synthesis.finalize_hook.write_output_manifest",
            return_value=None,
        ):
            with (
                patch(
                    "transcriptx.core.analysis.group_llm_synthesis.synthesize.build_ollama_analysis_client",
                    return_value=MagicMock(
                        generate=MagicMock(
                            return_value=json.dumps({"summary": "Second"})
                        )
                    ),
                ),
                patch(
                    "transcriptx.core.analysis.group_llm_synthesis.synthesize.require_ollama_analysis",
                ),
                patch(
                    "transcriptx.core.analysis.group_llm_synthesis.synthesize.resolve_llm_runtime",
                    return_value=_mock_runtime(),
                ),
            ):
                meta = run_synthesis_publish_and_manifest(
                    run_dir=run,
                    run_id="g2",
                    transcript_key="g",
                    selected_modules=["llm_summary"],
                    completed_agg_ids={"llm_summary"},
                    config=_cfg(),
                    aggregation_warnings=warnings,
                    already_holding_lock=True,
                )
    assert meta.get("published") is True
    # Prior generation must still exist (GC skipped on manifest failure)
    assert first_dir.is_dir()
    assert (first_dir / "COMMIT.json").is_file()


def test_inventory_digest_mismatch_resolver_none(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    _write_collect(run)
    gid = _publish_success(run)
    # Tamper artifact bytes without updating COMMIT inventory
    art = generation_dir(run, gid) / global_summary_rel()
    payload = json.loads(art.read_text(encoding="utf-8"))
    payload["summary"] = "tampered"
    art.write_text(json.dumps(payload), encoding="utf-8")
    assert load_group_llm_summary(run) is None


def test_symlink_escape_rejected(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    _write_collect(run)
    digests = compute_input_digests(
        global_collect_path=run / "llm_summary" / "llm_summary.json",
        speaker_rows_path=None,
    )
    gid = "escape_gen"
    gen = generation_dir(run, gid)
    (gen / "llm_summary").mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text(
        json.dumps(
            {
                "schema_id": SCHEMA_GLOBAL,
                "summary": "leaked",
                "generation_id": gid,
                **digests.as_dict(),
                "collect_schema_id": "x",
                "provenance": {},
            }
        ),
        encoding="utf-8",
    )
    target = gen / global_summary_rel()
    target.symlink_to(outside)
    from transcriptx.core.analysis.group_llm_synthesis.digests import sha256_file

    write_commit(
        run,
        generation_id=gid,
        digests=digests,
        overall_status="success",
        inventory=[
            {
                "rel_path": global_summary_rel(),
                "module": "llm_summary",
                "kind": "data_json",
                "sha256": sha256_file(outside),
            }
        ],
    )
    write_active(
        run,
        generation_id=gid,
        digests=digests,
        overall_status="success",
    )
    assert load_group_llm_summary(run) is None


def test_path_traversal_rel_rejected(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    _write_collect(run)
    digests = compute_input_digests(
        global_collect_path=run / "llm_summary" / "llm_summary.json",
        speaker_rows_path=None,
    )
    gid = "trav_gen"
    gen = generation_dir(run, gid)
    gen.mkdir(parents=True)
    # Plant a file outside generation but craft COMMIT rel with ..
    evil = run / "evil.json"
    evil.write_text("{}", encoding="utf-8")
    write_commit(
        run,
        generation_id=gid,
        digests=digests,
        overall_status="success",
        inventory=[
            {
                "rel_path": "../evil.json",
                "module": "llm_summary",
                "kind": "data_json",
                "sha256": "x",
            }
        ],
    )
    write_active(
        run,
        generation_id=gid,
        digests=digests,
        overall_status="success",
    )
    # load via private path would escape — public API only loads known rels
    from transcriptx.core.analysis.group_llm_synthesis.resolve import _load_artifact

    cache = ResolverCache()
    assert (
        _load_artifact(run, "../evil.json", expected_schema=SCHEMA_GLOBAL, cache=cache)
        is None
    )


def test_cancelled_never_in_active_commit(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    _write_collect(run)
    with synthesis_lock(run):
        result = run_group_llm_synthesis(
            run_root=run,
            run_id="g1",
            config=_cfg(),
            want_global=True,
            want_speakers=False,
            cancel_check=lambda: True,
        )
    assert result.attempt_status == "cancelled"
    assert result.published is False
    active = read_active(run)
    assert active is None or active.get("overall_status") != "cancelled"
    # No COMMIT for cancelled attempt generation (uncommitted)
    if result.generation_id:
        commit = generation_dir(run, result.generation_id) / "COMMIT.json"
        assert not commit.is_file()


def test_lock_timeout_leaves_active_unchanged(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    _write_collect(run)
    gid = _publish_success(run)
    before = read_active(run)
    assert before is not None
    assert before.get("generation_id") == gid

    warnings: list = []
    with patch(
        "transcriptx.core.analysis.group_llm_synthesis.finalize_hook.synthesis_lock",
        side_effect=SynthesisLockTimeout("timeout"),
    ):
        meta = run_synthesis_publish_and_manifest(
            run_dir=run,
            run_id="g3",
            transcript_key="g",
            selected_modules=["llm_summary"],
            completed_agg_ids={"llm_summary"},
            config=_cfg(),
            aggregation_warnings=warnings,
            already_holding_lock=False,
        )
    assert meta.get("attempt_status") == "lock_timeout"
    assert meta.get("published") is False
    assert any(w.get("code") == err.SYNTHESIS_LOCK_TIMEOUT for w in warnings)
    after = read_active(run)
    assert after is not None
    assert after.get("generation_id") == gid
    assert after.get("overall_status") != "cancelled"


def test_explicit_manifest_entries(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    _write_collect(run)
    _publish_success(run)
    with synthesis_lock(run):
        path = write_output_manifest(
            run_dir=run,
            run_id="g1",
            transcript_key="g",
            modules_enabled=["llm_summary"],
            synthesis_inventory_entries=None,
        )
    assert path is not None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    arts = manifest.get("artifacts") or []
    synth = [
        a
        for a in arts
        if str(a.get("rel_path") or "").startswith(".group_llm_synthesis/")
    ]
    assert synth, "expected explicit synthesis manifest entries"
    assert all(a.get("module") for a in synth)
    assert all(a.get("kind") in {"data_json", "data_txt"} for a in synth)
    # No duplicate scan noise with wrong module name
    assert not any(a.get("module") == ".group_llm_synthesis" for a in arts)


def test_gc_after_manifest_only(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    _write_collect(run)
    first = _publish_success(run)
    # Second publish
    second = _publish_success(run)
    assert first != second
    # Manually GC as finalize would after successful manifest
    gc_old_committed_generations(run, active_generation_id=second)
    assert not (generations_dir(run) / first).exists()
    assert (generations_dir(run) / second).is_dir()


def test_shared_resolver_cache_reuses_commit(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    _write_collect(run)
    _publish_success(run)
    cache = ResolverCache()
    a = load_group_llm_summary(run, cache=cache)
    b = load_group_llm_summary(run, cache=cache)
    assert a is not None and b is not None
    assert cache.valid is True


def _simulate_interrupted_mid_synthesis(run: Path) -> str:
    """Leave a partial generation like a SIGTERM mid-speaker loop (no COMMIT/ACTIVE)."""
    from transcriptx.core.analysis.group_llm_synthesis.paths import active_path

    _write_collect(run)
    gid = "interrupted_gen"
    gen = generation_dir(run, gid)
    (gen / "llm_summary").mkdir(parents=True)
    (gen / "llm_speaker_summary" / "group_llm_speaker_summaries").mkdir(parents=True)
    # Global written, only one speaker finished — mirrors the live abort.
    (gen / global_summary_rel()).write_text(
        json.dumps(
            {
                "schema_id": SCHEMA_GLOBAL,
                "summary": "Partial rollup never committed",
                "generation_id": gid,
            }
        ),
        encoding="utf-8",
    )
    speaker_json = (
        gen
        / "llm_speaker_summary"
        / "group_llm_speaker_summaries"
        / "Glen_partial_group_llm_speaker_summary.json"
    )
    speaker_json.write_text('{"summary": "Glen partial"}', encoding="utf-8")
    # Stale lock files left after process death (seen on host recovery).
    root = synthesis_root(run)
    root.mkdir(parents=True, exist_ok=True)
    lock_path(run).write_text("", encoding="utf-8")
    (root / f"{LOCK_FILENAME}.lock").write_text("", encoding="utf-8")
    assert not (gen / "COMMIT.json").is_file()
    assert not active_path(run).is_file()
    return gid


def test_interrupted_mid_synthesis_unavailable_until_commit(tmp_path: Path):
    """SIGTERM mid-synthesis must not expose partial artifacts via the resolver."""
    run = tmp_path / "run"
    run.mkdir()
    gid = _simulate_interrupted_mid_synthesis(run)
    assert load_group_llm_summary(run) is None
    assert read_active(run) is None
    assert (generation_dir(run, gid) / global_summary_rel()).is_file()


def test_recover_after_interrupted_synthesis_gc_and_republish(tmp_path: Path):
    """Recovery path used after live SIGTERM: GC uncommitted + re-publish + manifest."""
    run = tmp_path / "run"
    run.mkdir()
    gid = _simulate_interrupted_mid_synthesis(run)
    assert load_group_llm_summary(run) is None

    removed = gc_uncommitted_generations(run)
    assert gid in removed
    assert not generation_dir(run, gid).exists()

    warnings: list = []
    with synthesis_lock(run):
        with (
            patch(
                "transcriptx.core.analysis.group_llm_synthesis.synthesize.build_ollama_analysis_client",
                return_value=MagicMock(
                    generate=MagicMock(
                        return_value=json.dumps({"summary": "Recovered rollup"})
                    )
                ),
            ),
            patch(
                "transcriptx.core.analysis.group_llm_synthesis.synthesize.require_ollama_analysis",
            ),
            patch(
                "transcriptx.core.analysis.group_llm_synthesis.synthesize.resolve_llm_runtime",
                return_value=_mock_runtime(),
            ),
        ):
            meta = run_synthesis_publish_and_manifest(
                run_dir=run,
                run_id="recover1",
                transcript_key="g",
                selected_modules=["llm_summary"],
                completed_agg_ids={"llm_summary"},
                config=_cfg(),
                aggregation_warnings=warnings,
                already_holding_lock=True,
            )

    assert meta.get("published") is True
    assert meta.get("attempt_status") == "success"
    assert meta.get("overall_status") == "success"
    active = read_active(run)
    assert active is not None
    assert active.get("overall_status") == "success"
    assert active.get("generation_id") == meta.get("generation_id")
    loaded = load_group_llm_summary(run)
    assert loaded is not None
    assert loaded["summary"] == "Recovered rollup"
    assert (run / "manifest.json").is_file()
    # Leftover empty lock files must not block a subsequent lock acquisition.
    with synthesis_lock(run, timeout=2.0):
        pass


def test_stale_empty_lock_files_do_not_block_acquire(tmp_path: Path):
    """Abandoned 0-byte lock sidecars from a killed finalize must be re-acquirable."""
    run = tmp_path / "run"
    run.mkdir()
    root = synthesis_root(run)
    root.mkdir(parents=True, exist_ok=True)
    lock_path(run).write_bytes(b"")
    (root / f"{LOCK_FILENAME}.lock").write_bytes(b"")
    with synthesis_lock(run, timeout=2.0):
        acquired = True
    assert acquired
