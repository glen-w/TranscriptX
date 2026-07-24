"""Shared fixtures and AppTest helpers for GUI acceptance journeys."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from streamlit.testing.v1 import AppTest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MINI_TRANSCRIPT = _REPO_ROOT / "tests" / "fixtures" / "mini_transcriptx.json"
_MINIMAL_RUN = _REPO_ROOT / "tests" / "fixtures" / "composition" / "minimal_run"


@dataclass(frozen=True)
class GuiWorkspace:
    """Isolated filesystem roots for one AppTest journey."""

    root: Path
    data_dir: Path
    transcripts_dir: Path
    outputs_dir: Path
    config_dir: Path
    speaker_profiles_dir: Path
    groups_dir: Path
    slug: str | None = None
    transcript_path: Path | None = None
    import_id: str | None = None
    run_id: str | None = None
    run_root: Path | None = None
    profile_id: str | None = None
    group_id: str | None = None


def _mkdirs(ws: GuiWorkspace) -> None:
    for path in (
        ws.data_dir,
        ws.transcripts_dir,
        ws.transcripts_dir / "imports",
        ws.transcripts_dir / "originals",
        ws.transcripts_dir / "metadata" / "speaker_maps",
        ws.outputs_dir,
        ws.outputs_dir / "groups",
        ws.config_dir / "profiles",
        ws.speaker_profiles_dir,
        ws.groups_dir,
        ws.data_dir / "state",
        ws.data_dir / "recordings" / "imports",
    ):
        path.mkdir(parents=True, exist_ok=True)


def isolate_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> GuiWorkspace:
    """Point PATHS + import/group aliases at an isolated temp tree."""
    from dataclasses import replace as dc_replace

    import transcriptx.core.services.group_service as group_service_module
    import transcriptx.core.store.group_manifest_store as group_store_module
    import transcriptx.core.utils.paths as paths_mod
    from transcriptx.core.store.group_manifest_store import GroupManifestStore

    root = tmp_path / "gui_ws"
    data_dir = root / "data"
    transcripts_dir = data_dir / "transcripts"
    outputs_dir = data_dir / "outputs"
    config_dir = root / "config"
    speaker_profiles_dir = data_dir / "speaker_profiles"
    groups_dir = data_dir / "groups"

    ws = GuiWorkspace(
        root=root,
        data_dir=data_dir,
        transcripts_dir=transcripts_dir,
        outputs_dir=outputs_dir,
        config_dir=config_dir,
        speaker_profiles_dir=speaker_profiles_dir,
        groups_dir=groups_dir,
    )
    _mkdirs(ws)

    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TRANSCRIPTX_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("TRANSCRIPTX_OUTPUT_DIR", str(outputs_dir))
    monkeypatch.setenv("TRANSCRIPTX_TRANSCRIPTS_DIR", str(transcripts_dir))
    monkeypatch.setenv("TRANSCRIPTX_SPEAKER_PROFILES_DIR", str(speaker_profiles_dir))

    built = paths_mod._build_paths()
    built = dc_replace(
        built,
        project_root=root,
        data_dir=data_dir,
        speaker_profiles_dir=speaker_profiles_dir,
        config_dir=config_dir,
        profiles_dir=config_dir / "profiles",
        transcripts_dir=transcripts_dir,
        transcripts_imports_dir=transcripts_dir / "imports",
        transcripts_originals_dir=transcripts_dir / "originals",
        transcripts_metadata_dir=transcripts_dir / "metadata",
        transcripts_speaker_maps_dir=transcripts_dir / "metadata" / "speaker_maps",
        readable_transcripts_dir=transcripts_dir / "readable",
        outputs_dir=outputs_dir,
        group_outputs_dir=outputs_dir / "groups",
        state_dir=data_dir / "state",
        processing_state_file=data_dir / "state" / "processing_state.json",
        speaker_profiles_lock_file=data_dir / "state" / "speaker_profiles.lock",
        recordings_dir=data_dir / "recordings",
        recordings_imports_dir=data_dir / "recordings" / "imports",
    )
    monkeypatch.setattr(paths_mod, "PATHS", built)
    for name, value in (
        ("PROJECT_ROOT", built.project_root),
        ("DATA_DIR", built.data_dir),
        ("CONFIG_DIR", built.config_dir),
        ("DIARISED_TRANSCRIPTS_DIR", built.transcripts_dir),
        ("TRANSCRIPTS_IMPORTS_DIR", built.transcripts_imports_dir),
        ("TRANSCRIPTS_ORIGINALS_DIR", built.transcripts_originals_dir),
        ("TRANSCRIPTS_METADATA_DIR", built.transcripts_metadata_dir),
        ("TRANSCRIPTS_SPEAKER_MAPS_DIR", built.transcripts_speaker_maps_dir),
        ("OUTPUTS_DIR", built.outputs_dir),
        ("GROUP_OUTPUTS_DIR", built.group_outputs_dir),
        ("PROFILES_DIR", built.profiles_dir),
        ("RECORDINGS_DIR", built.recordings_dir),
        ("RECORDINGS_IMPORTS_DIR", built.recordings_imports_dir),
    ):
        monkeypatch.setattr(paths_mod, name, value)

    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.DIARISED_TRANSCRIPTS_DIR",
        transcripts_dir,
        raising=False,
    )
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.TRANSCRIPTS_ORIGINALS_DIR",
        transcripts_dir / "originals",
        raising=False,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_admission.DIARISED_TRANSCRIPTS_DIR",
        transcripts_dir,
        raising=False,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_admission.TRANSCRIPTS_IMPORTS_DIR",
        transcripts_dir / "imports",
        raising=False,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR",
        transcripts_dir,
        raising=False,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR",
        transcripts_dir / "metadata",
        raising=False,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.file_discovery.DIARISED_TRANSCRIPTS_DIR",
        transcripts_dir,
        raising=False,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.file_discovery.RECORDINGS_DIR",
        data_dir / "recordings",
        raising=False,
    )
    # Prefer isolated transcripts over the live config default_transcript_folder.
    monkeypatch.setattr(
        "transcriptx.core.utils.file_discovery._resolve_transcript_discovery_root",
        lambda root=None: Path(root) if root is not None else transcripts_dir,
    )

    monkeypatch.setattr(group_store_module, "PROJECT_ROOT", root, raising=False)
    monkeypatch.setattr(group_store_module, "_GROUPS_DIR", groups_dir, raising=False)
    monkeypatch.setattr(group_service_module, "PROJECT_ROOT", root, raising=False)
    monkeypatch.setattr(
        group_service_module, "_STORE", GroupManifestStore(), raising=False
    )

    try:
        from transcriptx.web.cache_helpers import clear_transcript_listing_caches

        clear_transcript_listing_caches()
    except Exception:
        pass

    return ws


def seed_managed_transcript(ws: GuiWorkspace) -> GuiWorkspace:
    """Import mini_transcriptx.json into the isolated library."""
    from transcriptx.io.managed_import_workflow import run_managed_import_workflow
    from transcriptx.web.cache_helpers import clear_transcript_listing_caches

    staging = ws.transcripts_dir / "imports" / f"{uuid4().hex}_mini_transcriptx.json"
    staging.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(_MINI_TRANSCRIPT, staging)
    result = run_managed_import_workflow(
        staging,
        logical_upload_basename="mini_transcriptx.json",
        overwrite=False,
    )
    clear_transcript_listing_caches()
    slug = result.json_path.stem
    return replace(
        ws,
        slug=slug,
        transcript_path=result.json_path,
        import_id=result.import_id,
    )


def seed_succeeded_run(
    ws: GuiWorkspace, *, run_id: str = "20240101_120000"
) -> GuiWorkspace:
    """Copy composition/minimal_run under outputs/<slug>/<run_id>."""
    if ws.slug is None:
        raise ValueError("seed_managed_transcript first")
    if not _MINIMAL_RUN.is_dir():
        pytest.skip("minimal_run fixture missing")
    run_root = ws.outputs_dir / ws.slug / run_id
    if run_root.exists():
        shutil.rmtree(run_root)
    shutil.copytree(_MINIMAL_RUN, run_root)
    # Keep run_id consistent with directory name for Overview display.
    manifest_path = run_root / "manifest.json"
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["run_id"] = run_id
        payload.setdefault("manifest_type", "artifact_manifest")
        if isinstance(payload.get("run_metadata"), dict):
            payload["run_metadata"]["run_id"] = run_id
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        manifest_path.write_text(
            json.dumps(
                {
                    "manifest_type": "artifact_manifest",
                    "schema_version": 1,
                    "run_id": run_id,
                    "artifacts": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    rr_path = run_root / "run_results.json"
    if rr_path.exists():
        rr = json.loads(rr_path.read_text(encoding="utf-8"))
        rr["run_id"] = run_id
        rr_path.write_text(json.dumps(rr, indent=2), encoding="utf-8")
    return replace(ws, run_id=run_id, run_root=run_root)


def write_run_results(run_root: Path, payload: dict[str, Any]) -> None:
    (run_root / "run_results.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def seed_partial_run(ws: GuiWorkspace) -> GuiWorkspace:
    """Succeeded artifact tree + skipped-only execution → Partial success."""
    ws = seed_succeeded_run(ws, run_id="20240101_130000")
    assert ws.run_root is not None
    write_run_results(
        ws.run_root,
        {
            "schema_version": 1,
            "run_id": ws.run_id,
            "transcript_key": ws.slug or "mini_transcriptx",
            "modules_enabled": ["stats", "summary"],
            "modules_run": [],
            "modules_failed": [],
            "modules_skipped": [
                {"module": "stats", "execution_status": "skipped"},
                {"module": "summary", "execution_status": "skipped"},
            ],
            "errors": [],
            "module_outcomes": [],
        },
    )
    return ws


def seed_failed_run(ws: GuiWorkspace) -> GuiWorkspace:
    """Succeeded artifact tree + module failures → 1 module failed / issues."""
    ws = seed_succeeded_run(ws, run_id="20240101_140000")
    assert ws.run_root is not None
    write_run_results(
        ws.run_root,
        {
            "schema_version": 1,
            "run_id": ws.run_id,
            "transcript_key": ws.slug or "mini_transcriptx",
            "modules_enabled": ["stats", "summary"],
            "modules_run": ["stats"],
            "modules_failed": ["summary"],
            "modules_skipped": [],
            "errors": [],
            "module_outcomes": [
                {
                    "module_id": "summary",
                    "error_code": "X",
                    "error_message": "boom",
                },
                {"module_id": "stats", "status": "succeeded"},
            ],
        },
    )
    return ws


def seed_speaker_profile(ws: GuiWorkspace, *, name: str = "Ada") -> GuiWorkspace:
    """Write a minimal file-backed speaker profile under the isolated root."""
    from transcriptx.core.speaker_profiles.layout import profile_path
    from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
    from transcriptx.core.speaker_profiles.store_io import (
        dumps_model,
        ensure_layout,
        utc_now_iso,
        write_bytes_under_root,
    )

    root = ws.speaker_profiles_dir
    ensure_layout(root)
    pid = str(uuid4())
    now = utc_now_iso()
    write_bytes_under_root(
        profile_path(pid, root=root),
        dumps_model(
            SpeakerProfileV1(
                profile_id=pid,
                display_name=name,
                created_at=now,
                updated_at=now,
            )
        ),
        root=root,
    )
    return replace(ws, profile_id=pid)


def seed_group(ws: GuiWorkspace, *, name: str = "GUI Acceptance Group") -> GuiWorkspace:
    """Create a file-backed group with the seeded transcript as sole member."""
    from transcriptx.core.services.group_service import GroupService

    if ws.transcript_path is None:
        raise ValueError("seed_managed_transcript first")
    group, _created = GroupService.create_or_get_group_with_status(
        name=name,
        group_type="group",
        transcript_refs=[str(ws.transcript_path)],
    )
    return replace(ws, group_id=group.group_id)


def markdown_blob(at: AppTest) -> str:
    """Flatten markdown + caption + text widget values for substring asserts."""
    parts: list[str] = []
    for attr in ("markdown", "caption", "text", "title", "header", "subheader"):
        for el in getattr(at, attr, []):
            val = getattr(el, "value", None)
            if val is not None:
                parts.append(str(val))
    return "\n".join(parts)


def assert_no_exception(at: AppTest) -> None:
    if at.exception:
        raise AssertionError(f"AppTest raised: {list(at.exception)}")


def run_page(
    module: str,
    func_name: str,
    *,
    session: dict[str, Any] | None = None,
    default_timeout: float = 30.0,
    script_dir: Path | None = None,
) -> AppTest:
    """Run ``module.func_name`` under live Streamlit AppTest via a temp script.

    ``AppTest.from_function`` cannot close over callables reliably (source rewrite),
    so we write a tiny import script instead.
    """
    import tempfile

    body = f"from {module} import {func_name}\n" f"{func_name}()\n"
    if script_dir is not None:
        script_dir.mkdir(parents=True, exist_ok=True)
        script_path = script_dir / f"apptest_{func_name}.py"
        script_path.write_text(body, encoding="utf-8")
    else:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        )
        tmp.write(body)
        tmp.flush()
        tmp.close()
        script_path = Path(tmp.name)

    at = AppTest.from_file(str(script_path), default_timeout=default_timeout)
    if session:
        for key, value in session.items():
            at.session_state[key] = value
    at.run()
    return at


def run_script(
    script_path: Path,
    *,
    session: dict[str, Any] | None = None,
    default_timeout: float = 30.0,
) -> AppTest:
    """Run a committed AppTest entry script (for multi-arg / env-driven pages)."""
    at = AppTest.from_file(str(script_path), default_timeout=default_timeout)
    if session:
        for key, value in session.items():
            at.session_state[key] = value
    at.run()
    return at


def stub_analysis_success(
    monkeypatch: pytest.MonkeyPatch, *, run_dir: Path
) -> list[Any]:
    """Stub AnalysisController so Run Analysis does not execute real pipelines."""
    from transcriptx.app.controllers import analysis_controller as ac_mod
    from transcriptx.app.models.results import AnalysisResult

    calls: list[Any] = []

    def _ok_result() -> AnalysisResult:
        run_dir.mkdir(parents=True, exist_ok=True)
        return AnalysisResult(
            success=True,
            run_dir=run_dir,
            manifest_path=run_dir / "manifest.json",
            modules_executed=["stats"],
            warnings=[],
            errors=[],
        )

    class _Ctrl:
        def validate_readiness(self, request: Any) -> list[str]:
            calls.append(("validate", request))
            return []

        def validate_group_readiness(self, request: Any) -> list[str]:
            calls.append(("validate_group", request))
            return []

        def run_analysis(self, request: Any, **_kwargs: Any) -> Any:
            calls.append(("run", request))
            return _ok_result()

        def run_group_analysis(self, request: Any, **_kwargs: Any) -> Any:
            calls.append(("run_group", request))
            return _ok_result()

    monkeypatch.setattr(ac_mod, "AnalysisController", _Ctrl)
    return calls
