"""
Smoke tests for every analysis module.

Runs the pipeline with a single module and a small fixture to catch regressions
quickly. Core-available, non-audio modules always run; modules that require
optional extras run only when those extras are installed.
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
# - contagion: depends on emotion signal reconstruction and can fail when NLTK
#   tokenization resources are unavailable in lightweight smoke environments
SMOKE_SKIP_MODULES: frozenset[str] = frozenset(
    {
        "contagion",
        "qa_analysis",
        "momentum",
        "moments",
        "summary",
        "topic_modeling",
        "understandability",
        "wordclouds",
        # LLM modules require a running Ollama daemon; covered by unit/integration tests.
        "llm_summary",
        "llm_speaker_summary",
        "narrative_summary",
        "llm_action_items",
        "llm_custom_qa",
    }
)

# Modules that call spaCy NLP runtime even without required_extras={"nlp"}.
# Core+dev CI does not install [nlp]; cover these under nlp-enabled lanes instead.
_SPACY_RUNTIME_MODULES: frozenset[str] = frozenset(
    {
        "insight_eligibility",
        "highlights",
        "bertopic",
        "insights",
        "topic_modeling",
    }
)


def _nlp_extra_available() -> bool:
    from transcriptx.core.pipeline.module_registry import is_extra_available

    return is_extra_available("nlp")


def _core_modules_no_audio() -> list[str]:
    """True-core transcript modules for Core+dev smoke (no optional extras)."""
    from transcriptx.core.pipeline.module_registry import (
        get_available_modules,
        get_module_info,
        is_extra_available,
    )

    core = set(get_available_modules(core_mode=True))
    nlp_ok = _nlp_extra_available()

    def _ready(module_name: str, seen: set[str] | None = None) -> bool:
        if module_name not in core:
            return False
        info = get_module_info(module_name)
        if info is None or info.requires_audio:
            return False
        seen = seen or set()
        if module_name in seen:
            return False
        seen.add(module_name)
        for dep in getattr(info, "dependencies", []) or []:
            if dep not in core or not _ready(dep, seen):
                return False
        return True

    selected: list[str] = []
    for module_name in sorted(core):
        if module_name in SMOKE_SKIP_MODULES or not _ready(module_name):
            continue
        info = get_module_info(module_name)
        assert info is not None
        # Optional-extra modules are covered by test_optional_module_smoke_*.
        if info.required_extras:
            continue
        if module_name in _SPACY_RUNTIME_MODULES and not nlp_ok:
            continue
        # Skip when a declared dependency's extras are missing (defensive).
        if any(
            (dep_info := get_module_info(dep))
            and dep_info.required_extras
            and not all(is_extra_available(e) for e in dep_info.required_extras)
            for dep in (info.dependencies or [])
        ):
            continue
        selected.append(module_name)
    return selected


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
        and m not in SMOKE_SKIP_MODULES
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
    """Each core-available non-audio module runs successfully on mini_transcript."""
    _run_pipeline_smoke(tmp_path, monkeypatch, _fixture_path, module_name)


@pytest.mark.smoke
@pytest.mark.parametrize("module_name", _optional_module_ids(), ids=lambda x: x)
def test_optional_module_smoke_when_extra_available(
    tmp_path, monkeypatch, _fixture_path, module_name: str
) -> None:
    """Modules with required_extras run when those extras are installed; otherwise skipped."""
    from transcriptx.core.pipeline.module_registry import get_module_info
    from transcriptx.core.pipeline.optional_extras import is_extra_distribution_present

    info = get_module_info(module_name)
    if not info or not info.required_extras:
        pytest.skip("not an optional-extra module")
    # Non-importing probe: importing bertopic/UMAP here would init Numba before
    # pipeline thread pins and break fit_transform (NUMBA_NUM_THREADS sticky).
    if not all(is_extra_distribution_present(e) for e in info.required_extras):
        pytest.skip(f"optional extras not installed: {sorted(info.required_extras)}")
    if module_name in _SPACY_RUNTIME_MODULES and not _nlp_extra_available():
        pytest.skip("requires transcriptx[nlp] (spaCy runtime)")
    _run_pipeline_smoke(tmp_path, monkeypatch, _fixture_path, module_name)
