from pathlib import Path


def _write_artifact_manifest(
    run_dir: Path, *, rel_paths: list[str], manifest_type: str = "artifact_manifest"
) -> None:
    import json

    artifacts = [
        {"id": f"id_{idx}", "rel_path": rel_path}
        for idx, rel_path in enumerate(rel_paths, start=1)
    ]
    payload = {
        "manifest_type": manifest_type,
        "schema_version": 1,
        "run_id": run_dir.name,
        "run_metadata": {},
        "artifacts": artifacts,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def test_file_service_is_viewable_run_requires_user_artifact(
    tmp_path: Path,
) -> None:
    from transcriptx.web.services.file_service import FileService

    run_dir = tmp_path / "run_a"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / ".transcriptx").mkdir(parents=True, exist_ok=True)
    (run_dir / ".transcriptx" / "manifest.json").write_text("{}", encoding="utf-8")

    assert FileService._is_viewable_run(run_dir) is False

    _write_artifact_manifest(run_dir, rel_paths=["run_results.json"])
    assert FileService._is_viewable_run(run_dir) is False

    _write_artifact_manifest(run_dir, rel_paths=["charts/summary.png"])
    assert FileService._is_viewable_run(run_dir) is True


def test_run_index_is_viewable_run_requires_user_artifact(tmp_path: Path) -> None:
    from transcriptx.web.services.run_index import RunIndex

    run_dir = tmp_path / "run_b"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / ".transcriptx").mkdir(parents=True, exist_ok=True)
    (run_dir / ".transcriptx" / "manifest.json").write_text("{}", encoding="utf-8")

    assert RunIndex._is_viewable_run(run_dir) is False

    _write_artifact_manifest(run_dir, rel_paths=["run_report.json"])
    assert RunIndex._is_viewable_run(run_dir) is False

    _write_artifact_manifest(
        run_dir, rel_paths=[".transcriptx/run_config_effective.json"]
    )
    assert RunIndex._is_viewable_run(run_dir) is False

    _write_artifact_manifest(run_dir, rel_paths=["stats/summary.json"])
    assert RunIndex._is_viewable_run(run_dir) is True
