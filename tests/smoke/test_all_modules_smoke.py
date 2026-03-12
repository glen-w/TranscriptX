"""
Smoke tests for every analysis module.

Runs the pipeline with a single module and a small fixture to catch regressions
quickly. Core modules (no optional deps, no audio) always run; modules that
require optional extras run only when those extras are installed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.target_resolver import TranscriptRef


# Modules that need special setup and are covered by contract/integration tests instead.
# - topic_modeling: needs min segment count for NMF/LDA (mini_transcript too small)
# - understandability: needs NLTK data (e.g. punkt_tab) which is not guaranteed in CI
# - wordclouds: slow/heavy in smoke (timeout); covered by contract tests
SMOKE_SKIP_MODULES: frozenset[str] = frozenset({
    "topic_modeling",
    "understandability",
    "wordclouds",
})


def _core_modules_no_audio() -> list[str]:
    """Module names that run in core mode and do not require audio (for transcript-only smoke)."""
    from transcriptx.core.pipeline.module_registry import (
        get_available_modules,
        get_module_info,
    )

    core = get_available_modules(core_mode=True)
    return [
        m
        for m in core
        if m not in SMOKE_SKIP_MODULES
        and not (get_module_info(m) and get_module_info(m).requires_audio)
    ]


def _optional_module_ids() -> list[str]:
    """Module names that have required_extras and do not require audio (tested when extras present)."""
    from transcriptx.core.pipeline.module_registry import (
        get_available_modules,
        get_module_info,
    )

    all_mods = get_available_modules(core_mode=False)
    return [
        m
        for m in all_mods
        if (info := get_module_info(m))
        and info.required_extras
        and not info.requires_audio
    ]


@pytest.fixture(scope="module")
def _fixture_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tests" / "fixtures" / "mini_transcript.json"
    assert path.exists(), f"Fixture missing: {path}"
    return path


def _run_pipeline_smoke(
    tmp_path, monkeypatch, fixture_path: Path, module_name: str
) -> None:
    from transcriptx.core.utils import output_standards as output_standards_module
    from transcriptx.core.utils import paths as paths_module
    from transcriptx.core.utils import transcript_output as transcript_output_module
    from transcriptx.core.pipeline import pipeline as pipeline_module

    outputs_root = tmp_path / "outputs"
    transcripts_root = tmp_path / "transcripts"
    outputs_root.mkdir()
    transcripts_root.mkdir()

    monkeypatch.setenv("TRANSCRIPTX_DISABLE_DOWNLOADS", "1")
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(paths_module, "GROUP_OUTPUTS_DIR", str(outputs_root / "groups"))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        output_standards_module, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root)
    )
    monkeypatch.setattr(transcript_output_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        transcript_output_module, "DIARISED_TRANSCRIPTS_DIR", str(transcripts_root)
    )
    monkeypatch.setattr(pipeline_module, "OUTPUTS_DIR", str(outputs_root))

    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=[module_name],
        persist=False,
    )

    assert result.get("errors") == [], f"Module {module_name}: {result.get('errors')}"
    output_dir = Path(result["output_dir"])
    assert output_dir.exists(), f"Module {module_name}: output_dir missing"
    manifest_path = output_dir / "manifest.json"
    assert manifest_path.exists(), f"Module {module_name}: manifest.json missing"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "artifacts" in manifest, f"Module {module_name}: manifest has no artifacts"


@pytest.mark.smoke
@pytest.mark.parametrize("module_name", _core_modules_no_audio(), ids=lambda x: x)
def test_core_module_smoke(
    tmp_path, monkeypatch, _fixture_path, module_name: str
) -> None:
    """Each core module (no optional deps, no audio) runs successfully on mini_transcript."""
    _run_pipeline_smoke(tmp_path, monkeypatch, _fixture_path, module_name)


@pytest.mark.smoke
@pytest.mark.parametrize("module_name", _optional_module_ids(), ids=lambda x: x)
def test_optional_module_smoke_when_extra_available(
    tmp_path, monkeypatch, _fixture_path, module_name: str
) -> None:
    """Modules with required_extras run when those extras are installed; otherwise skipped."""
    from transcriptx.core.pipeline.module_registry import (
        get_module_info,
        is_extra_available,
    )

    info = get_module_info(module_name)
    if not info or not info.required_extras:
        pytest.skip("not an optional-extra module")
    if not all(is_extra_available(e) for e in info.required_extras):
        pytest.skip(f"optional extras not installed: {sorted(info.required_extras)}")
    _run_pipeline_smoke(tmp_path, monkeypatch, _fixture_path, module_name)
