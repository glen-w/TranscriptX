import re
from pathlib import Path

from transcriptx.core.pipeline.module_registry import get_available_modules, get_determinism_tier
from transcriptx.core.utils.run_manifest import create_run_manifest


def _analysis_files() -> list[Path]:
    root = Path(__file__).resolve().parents[2] / "src" / "transcriptx" / "core" / "analysis"
    return [path for path in root.rglob("*.py") if path.name != "__init__.py"]


def test_analysis_modules_do_not_write_files_directly():
    write_open_pattern = re.compile(r"open\([^\\n]*[\"']w[\"']|open\([^\\n]*[\"']a[\"']|open\([^\\n]*[\"']x[\"']")
    path_write_pattern = re.compile(r"\.write_text\(|\.write_bytes\(")
    offenders = []
    for path in _analysis_files():
        content = path.read_text(encoding="utf-8")
        if write_open_pattern.search(content) or path_write_pattern.search(content):
            offenders.append(str(path))
    assert offenders == []


def test_analysis_modules_do_not_access_env_or_repos():
    env_pattern = re.compile(r"os\.environ|getenv\(")
    repo_pattern = re.compile(r"transcriptx\.database\.repositories|get_session\(")
    offenders = []
    for path in _analysis_files():
        content = path.read_text(encoding="utf-8")
        if env_pattern.search(content) or repo_pattern.search(content):
            offenders.append(str(path))
    assert offenders == []


def test_module_registry_determinism_tiers():
    for module in get_available_modules():
        tier = get_determinism_tier(module)
        assert tier in {"T0", "T1", "T2"}


def test_run_manifest_includes_required_fields(tmp_path: Path):
    transcript_path = tmp_path / "tiny.json"
    transcript_path.write_text('{"segments": []}', encoding="utf-8")
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = create_run_manifest(
        transcript_path=str(transcript_path),
        selected_modules=["stats"],
        execution_order=["stats"],
        modules_run=["stats"],
        errors=[],
        output_dir=str(output_dir),
        rerun_mode="reuse-existing-run",
    )

    manifest_dict = manifest.to_dict()
    assert manifest_dict.get("transcript_hash")
    assert manifest_dict.get("config_snapshot_hash") or manifest_dict.get("config_snapshot")
    assert manifest_dict.get("module_metadata")
    assert manifest_dict.get("artifacts") is not None
    assert manifest_dict.get("rerun_mode") == "reuse-existing-run"
