"""Keep-file salvage for DELETE_OLD cleanup."""

from __future__ import annotations

from pathlib import Path

from transcriptx.web.services.run_cleanup import (
    CONFIRM_DELETE_OLD,
    RETAINED_DIR_NAME,
    CleanupAuthorization,
    CleanupMode,
    CleanupRetainPolicy,
    CleanupStatus,
    RunCleanupService,
)


def _mk_run(root: Path, slug: str, run_id: str) -> Path:
    run = root / slug / run_id
    run.mkdir(parents=True, exist_ok=True)
    (run / "artifact.bin").write_text("heavy", encoding="utf-8")
    transcripts = run / "transcripts"
    transcripts.mkdir(parents=True, exist_ok=True)
    (transcripts / "meeting.txt").write_text("hello", encoding="utf-8")
    (transcripts / "meeting.csv").write_text("a,b\n", encoding="utf-8")
    (transcripts / "meeting.srt").write_text("1\n", encoding="utf-8")
    (transcripts / "meeting.vtt").write_text("WEBVTT\n", encoding="utf-8")
    (run / "report.md").write_text("# report\n", encoding="utf-8")
    (run / "report.txt").write_text("report\n", encoding="utf-8")
    (run / "deep" / "nested").mkdir(parents=True, exist_ok=True)
    (run / "deep" / "nested" / "foo_llm_summary.md").write_text(
        "summary", encoding="utf-8"
    )
    (run / "deep" / "nested" / "foo_llm_summary.json").write_text(
        "{}", encoding="utf-8"
    )
    (run / "other.json").write_text("{}", encoding="utf-8")
    return run


def _svc(tmp_path: Path) -> RunCleanupService:
    out = tmp_path / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    groups = out / "groups"
    groups.mkdir(parents=True, exist_ok=True)
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    for name in ("transcripts", "recordings", "corrections", "groups"):
        (data / name).mkdir(exist_ok=True)
    (data / "transcripts" / "metadata").mkdir(parents=True, exist_ok=True)
    return RunCleanupService(
        outputs_dir=out,
        group_outputs_dir=groups,
        state_dir=state,
        project_root=tmp_path,
        data_dir=data,
        config_dir=tmp_path / "config",
    )


def test_delete_old_salvages_keep_files(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    out = svc.outputs_dir
    older = "20200101_000000_00000001"
    newer = "20200102_000000_00000002"
    _mk_run(out, "slug_a", older)
    _mk_run(out, "slug_a", newer)

    retain = CleanupRetainPolicy(
        keep_human_readable=True, keep_llm_summaries=True
    )
    handle, preview = svc.preview_cleanup(
        CleanupMode.DELETE_OLD, "s1", retain_policy=retain
    )
    assert preview.run_count == 1
    result = svc.execute_cleanup(
        handle,
        CleanupAuthorization(
            acknowledged=True,
            phrase=CONFIRM_DELETE_OLD,
            mode=CleanupMode.DELETE_OLD,
            plan_id=preview.plan_id,
        ),
        "s1",
    )
    assert result.status is CleanupStatus.SUCCESS
    assert not (out / "slug_a" / older).exists()
    assert (out / "slug_a" / newer).exists()

    retained = out / "slug_a" / RETAINED_DIR_NAME / older
    assert (retained / "transcripts" / "meeting.txt").read_text(
        encoding="utf-8"
    ) == "hello"
    assert (retained / "transcripts" / "meeting.csv").exists()
    assert (retained / "transcripts" / "meeting.srt").exists()
    assert (retained / "transcripts" / "meeting.vtt").exists()
    assert (retained / "report.md").exists()
    assert (retained / "report.txt").exists()
    assert (retained / "deep" / "nested" / "foo_llm_summary.md").exists()
    assert (retained / "deep" / "nested" / "foo_llm_summary.json").exists()
    assert not (retained / "artifact.bin").exists()
    assert not (retained / "other.json").exists()


def test_retain_policy_changes_plan_id(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    _mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
    _mk_run(svc.outputs_dir, "slug_a", "20200102_000000_00000002")
    _, plain = svc.preview_cleanup(CleanupMode.DELETE_OLD, "plain")
    _, kept = svc.preview_cleanup(
        CleanupMode.DELETE_OLD,
        "kept",
        retain_policy=CleanupRetainPolicy(keep_human_readable=True),
    )
    assert plain.plan_id != kept.plan_id


def test_iter_keep_paths_unit(tmp_path: Path) -> None:
    from transcriptx.web.services.run_cleanup.retain import iter_keep_relative_paths

    run = _mk_run(tmp_path, "slug", "20200101_000000_00000001")
    rels = iter_keep_relative_paths(
        run,
        CleanupRetainPolicy(
            keep_human_readable=True, keep_llm_summaries=True
        ),
    )
    assert "transcripts/meeting.txt" in rels
    assert "report.md" in rels
    assert "deep/nested/foo_llm_summary.json" in rels
    assert "artifact.bin" not in rels
