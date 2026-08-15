"""Fixtures for live Streamlit Playwright GUI E2E."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import pytest

from tests.e2e_gui.helpers import DEFAULT_VIEWPORT, fixture_planning_review

_REPO_ROOT = Path(__file__).resolve().parents[2]
_APP_PY = _REPO_ROOT / "src" / "transcriptx" / "web" / "app.py"
_MINIMAL_RUN = _REPO_ROOT / "tests" / "fixtures" / "composition" / "minimal_run"
_PLANNING = fixture_planning_review()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "gui_e2e: Playwright E2E against live Streamlit GUI (tests/e2e_gui; included in default pytest)",
    )


def pytest_report_header(config: pytest.Config) -> list[str]:
    """Surface Playwright GUI E2E scope in pytest session logs."""
    return [
        "Playwright GUI E2E (gui_e2e): tests/e2e_gui — workflows "
        "first-analysis, speaker-identification, investigate-evidence, "
        "local-ai-synthesis surface, export-results, charts-view; "
        "included in default pytest (skips without Chromium)",
    ]


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    e2e_items = [i for i in items if i.get_closest_marker("gui_e2e")]
    if e2e_items:
        terminal = config.pluginmanager.get_plugin("terminalreporter")
        if terminal is not None:
            terminal.write_line(
                f"Playwright gui_e2e collected: {len(e2e_items)} test(s) "
                f"under tests/e2e_gui (default suite)"
            )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass(frozen=True)
class E2EWorkspace:
    """Isolated filesystem roots for one live Streamlit session."""

    root: Path
    data_dir: Path
    transcripts_dir: Path
    outputs_dir: Path
    config_dir: Path
    speaker_profiles_dir: Path
    groups_dir: Path
    env: dict[str, str]
    slug: str | None = None
    transcript_path: Path | None = None
    import_id: str | None = None
    run_id: str | None = None
    run_root: Path | None = None


def _mkdirs(ws: E2EWorkspace) -> None:
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
    # Occupied data roots without a marker trip the Streamlit schema-epoch gate.
    from transcriptx.core.utils.schema_epoch import write_epoch

    write_epoch(ws.data_dir)


def _workspace_env(ws_dirs: dict[str, Path]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "TRANSCRIPTX_DATA_DIR": str(ws_dirs["data_dir"]),
            "TRANSCRIPTX_CONFIG_DIR": str(ws_dirs["config_dir"]),
            "TRANSCRIPTX_OUTPUT_DIR": str(ws_dirs["outputs_dir"]),
            "TRANSCRIPTX_TRANSCRIPTS_DIR": str(ws_dirs["transcripts_dir"]),
            "TRANSCRIPTX_SPEAKER_PROFILES_DIR": str(ws_dirs["speaker_profiles_dir"]),
            "TRANSCRIPTX_DISABLE_DOWNLOADS": "1",
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
            "STREAMLIT_SERVER_HEADLESS": "true",
            # Prefer classic Speaker ID UI (no CCv2 workspace package required).
            "TX_SPEAKER_ID_WORKSPACE_COMPONENT": "0",
        }
    )
    return env


def _apply_paths_for_seeding(ws: E2EWorkspace) -> None:
    """Point in-process PATHS at the workspace so seeding APIs write correctly."""
    from dataclasses import replace as dc_replace

    import transcriptx.core.utils.paths as paths_mod

    for key, value in ws.env.items():
        os.environ[key] = value

    built = paths_mod._build_paths()
    built = dc_replace(
        built,
        project_root=ws.root,
        data_dir=ws.data_dir,
        speaker_profiles_dir=ws.speaker_profiles_dir,
        config_dir=ws.config_dir,
        profiles_dir=ws.config_dir / "profiles",
        transcripts_dir=ws.transcripts_dir,
        transcripts_imports_dir=ws.transcripts_dir / "imports",
        transcripts_originals_dir=ws.transcripts_dir / "originals",
        transcripts_metadata_dir=ws.transcripts_dir / "metadata",
        transcripts_speaker_maps_dir=ws.transcripts_dir / "metadata" / "speaker_maps",
        readable_transcripts_dir=ws.transcripts_dir / "readable",
        outputs_dir=ws.outputs_dir,
        group_outputs_dir=ws.outputs_dir / "groups",
        state_dir=ws.data_dir / "state",
        processing_state_file=ws.data_dir / "state" / "processing_state.json",
        speaker_profiles_lock_file=ws.data_dir / "state" / "speaker_profiles.lock",
        recordings_dir=ws.data_dir / "recordings",
        recordings_imports_dir=ws.data_dir / "recordings" / "imports",
    )
    paths_mod.PATHS = built
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
        setattr(paths_mod, name, value)

    # Keep managed import / discovery aligned with the isolated tree.
    path_aliases: list[tuple[str, str, Path]] = [
        (
            "transcriptx.io.managed_import_workflow",
            "DIARISED_TRANSCRIPTS_DIR",
            ws.transcripts_dir,
        ),
        (
            "transcriptx.io.managed_import_workflow",
            "TRANSCRIPTS_ORIGINALS_DIR",
            ws.transcripts_dir / "originals",
        ),
        (
            "transcriptx.io.import_admission",
            "DIARISED_TRANSCRIPTS_DIR",
            ws.transcripts_dir,
        ),
        (
            "transcriptx.io.import_admission",
            "TRANSCRIPTS_IMPORTS_DIR",
            ws.transcripts_dir / "imports",
        ),
        (
            "transcriptx.io.admit_and_register",
            "DIARISED_TRANSCRIPTS_DIR",
            ws.transcripts_dir,
        ),
        (
            "transcriptx.io.import_metadata.paths",
            "DIARISED_TRANSCRIPTS_DIR",
            ws.transcripts_dir,
        ),
        (
            "transcriptx.io.import_metadata.paths",
            "TRANSCRIPTS_METADATA_DIR",
            ws.transcripts_dir / "metadata",
        ),
        (
            "transcriptx.core.utils.file_discovery",
            "DIARISED_TRANSCRIPTS_DIR",
            ws.transcripts_dir,
        ),
        (
            "transcriptx.core.utils.slug_manager",
            "OUTPUTS_DIR",
            ws.outputs_dir,
        ),
        (
            "transcriptx.core.utils.slug_manager",
            "INDEX_FILE",
            ws.outputs_dir / ".transcriptx_index.json",
        ),
    ]
    for mod_path, attr, value in path_aliases:
        module = __import__(mod_path, fromlist=[attr])
        setattr(module, attr, value)


def create_workspace(tmp_path: Path) -> E2EWorkspace:
    root = tmp_path / "e2e_ws"
    data_dir = root / "data"
    transcripts_dir = data_dir / "transcripts"
    outputs_dir = data_dir / "outputs"
    config_dir = root / "config"
    speaker_profiles_dir = data_dir / "speaker_profiles"
    groups_dir = data_dir / "groups"
    dirs = {
        "data_dir": data_dir,
        "transcripts_dir": transcripts_dir,
        "outputs_dir": outputs_dir,
        "config_dir": config_dir,
        "speaker_profiles_dir": speaker_profiles_dir,
    }
    env = _workspace_env(dirs)
    ws = E2EWorkspace(
        root=root,
        data_dir=data_dir,
        transcripts_dir=transcripts_dir,
        outputs_dir=outputs_dir,
        config_dir=config_dir,
        speaker_profiles_dir=speaker_profiles_dir,
        groups_dir=groups_dir,
        env=env,
    )
    _mkdirs(ws)
    return ws


def seed_planning_transcript(ws: E2EWorkspace) -> E2EWorkspace:
    """Import + register planning_review.json into the isolated library.

    Uses ``admit_and_register`` so the slug index is written — required for the
    live Streamlit sidebar transcript picker (Library file discovery alone is
    not enough for VIEW pages that need ``subject_id``).
    """
    if not _PLANNING.is_file():
        pytest.skip(f"planning_review fixture missing: {_PLANNING}")

    _apply_paths_for_seeding(ws)
    from transcriptx.io.admit_and_register import AdmitOutcomeKind, admit_and_register

    staging = ws.transcripts_dir / "imports" / f"{uuid4().hex}_planning_review.json"
    staging.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(_PLANNING, staging)
    outcome = admit_and_register(
        staging,
        logical_basename="planning_review.json",
    )
    if outcome.kind not in {
        AdmitOutcomeKind.IMPORTED_AND_REGISTERED,
        AdmitOutcomeKind.PARTIAL_STATE_REPAIRED,
        AdmitOutcomeKind.REGISTRATION_RECOVERED,
        AdmitOutcomeKind.ALREADY_MANAGED,
    }:
        raise RuntimeError(
            f"admit_and_register failed: {outcome.kind} {outcome.user_safe_detail}"
        )
    assert outcome.transcript_path is not None
    slug = outcome.slug or outcome.transcript_path.stem
    return replace(
        ws,
        slug=slug,
        transcript_path=outcome.transcript_path,
        import_id=None,
    )


def seed_succeeded_run(
    ws: E2EWorkspace, *, run_id: str = "20240101_120000"
) -> E2EWorkspace:
    """Copy composition/minimal_run under outputs/<slug>/<run_id>."""
    if ws.slug is None:
        raise ValueError("seed_planning_transcript first")
    if not _MINIMAL_RUN.is_dir():
        pytest.skip("minimal_run fixture missing")
    run_root = ws.outputs_dir / ws.slug / run_id
    if run_root.exists():
        shutil.rmtree(run_root)
    shutil.copytree(_MINIMAL_RUN, run_root)
    manifest_path = run_root / "manifest.json"
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["run_id"] = run_id
        payload.setdefault("manifest_type", "artifact_manifest")
        if isinstance(payload.get("run_metadata"), dict):
            payload["run_metadata"]["run_id"] = run_id
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    rr_path = run_root / "run_results.json"
    if rr_path.exists():
        rr = json.loads(rr_path.read_text(encoding="utf-8"))
        rr["run_id"] = run_id
        rr_path.write_text(json.dumps(rr, indent=2), encoding="utf-8")
    return replace(ws, run_id=run_id, run_root=run_root)


@dataclass
class LiveApp:
    workspace: E2EWorkspace
    base_url: str
    port: int
    process: subprocess.Popen


def _wait_health(base_url: str, *, timeout_s: float = 90.0) -> None:
    import urllib.error
    import urllib.request

    health = f"{base_url}/_stcore/health"
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=2) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_err = exc
            time.sleep(0.5)
    raise RuntimeError(f"Streamlit health check failed for {health}: {last_err}")


def start_streamlit(ws: E2EWorkspace) -> LiveApp:
    if not _APP_PY.is_file():
        raise FileNotFoundError(_APP_PY)
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(_APP_PY),
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(_REPO_ROOT),
        env=ws.env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_health(base_url)
    except Exception:
        # Dump launcher output for debugging, then re-raise.
        try:
            out, _ = proc.communicate(timeout=2)
        except Exception:
            out = ""
            proc.kill()
        raise RuntimeError(
            f"Failed to start Streamlit on {base_url}. Output:\n{out[-4000:]}"
        ) from None
    return LiveApp(workspace=ws, base_url=base_url, port=port, process=proc)


def stop_streamlit(app: LiveApp) -> None:
    proc = app.process
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


@pytest.fixture
def e2e_workspace(tmp_path: Path) -> E2EWorkspace:
    return create_workspace(tmp_path)


@pytest.fixture
def live_app(e2e_workspace: E2EWorkspace) -> Iterator[LiveApp]:
    """Empty workspace + live Streamlit (for import-from-UI journeys)."""
    app = start_streamlit(e2e_workspace)
    try:
        yield app
    finally:
        stop_streamlit(app)


@pytest.fixture
def seeded_app(e2e_workspace: E2EWorkspace) -> Iterator[LiveApp]:
    """Workspace with planning_review imported before Streamlit starts."""
    ws = seed_planning_transcript(e2e_workspace)
    app = start_streamlit(ws)
    try:
        yield app
    finally:
        stop_streamlit(app)


@pytest.fixture
def seeded_run_app(e2e_workspace: E2EWorkspace) -> Iterator[LiveApp]:
    """Workspace with planning_review + completed minimal_run before Streamlit."""
    ws = seed_succeeded_run(seed_planning_transcript(e2e_workspace))
    app = start_streamlit(ws)
    try:
        yield app
    finally:
        stop_streamlit(app)


@pytest.fixture
def page(pytestconfig):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as exc:  # noqa: BLE001 — environment capability gate
            pytest.skip(f"Playwright Chromium unavailable: {exc}")
        context = browser.new_context(viewport=DEFAULT_VIEWPORT)
        pg = context.new_page()
        yield pg
        context.close()
        browser.close()
