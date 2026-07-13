"""
Smoke test: analysis pipeline runs without Docker or socket.

Validates that the core product (load transcript -> run modules -> write artifacts)
works with no Docker dependency. Used to guard against re-coupling to Docker.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.target_resolver import TranscriptRef


def _artifact_rel_path_for_module(manifest: dict, module: str, suffix: str) -> str:
    for artifact in manifest.get("artifacts", []):
        if artifact.get("module") != module:
            continue
        rel_path = str(artifact.get("rel_path", ""))
        if rel_path.endswith(suffix):
            return rel_path
    raise AssertionError(f"Missing artifact for module={module} with suffix={suffix}")


@pytest.mark.smoke
def test_analysis_runs_without_docker(tmp_path, monkeypatch) -> None:
    """Load a fixture transcript, run stats module, assert outputs. No Docker socket needed."""
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

    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "tests"
        / "fixtures"
        / "mini_transcript.json"
    )
    assert fixture_path.exists(), f"Fixture missing: {fixture_path}"

    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=["stats"],
        persist=False,
    )

    assert result.get("errors") == [], result.get("errors")
    output_dir = Path(result["output_dir"])
    assert output_dir.exists()
    manifest_path = output_dir / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "artifacts" in manifest


@pytest.mark.smoke
def test_insight_stack_contract_smoke(tmp_path, monkeypatch) -> None:
    """Run insight stack end-to-end and assert core output contracts."""
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

    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "tests"
        / "fixtures"
        / "mini_transcript.json"
    )
    assert fixture_path.exists(), f"Fixture missing: {fixture_path}"

    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=[
            "tics",
            "insight_eligibility",
            "topic_modeling",
            "highlights",
            "insights",
        ],
        persist=False,
    )

    assert result.get("errors") == [], result.get("errors")
    run_dir = Path(result["output_dir"])
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    insight_rel = _artifact_rel_path_for_module(manifest, "insights", "_insights.json")
    insights_payload = json.loads((run_dir / insight_rel).read_text(encoding="utf-8"))
    assert "rejected_topics_debug" not in insights_payload
    banned_content_terms = {
        "i",
        "it",
        "we",
        "you",
        "he",
        "she",
        "kind of",
        "i mean",
        "of course",
        "for example",
        "need to",
        "going to",
        "we need",
    }
    key_theme_phrases = {
        str(row.get("phrase", "")).lower()
        for row in insights_payload.get("key_themes", [])
        if isinstance(row, dict)
    }
    recurring_phrases = {
        str(row.get("phrase", "")).lower()
        for row in insights_payload.get("recurring_ideas", [])
        if isinstance(row, dict)
    }
    assert key_theme_phrases.isdisjoint(banned_content_terms)
    assert recurring_phrases.isdisjoint(banned_content_terms)

    highlights_rel = _artifact_rel_path_for_module(
        manifest, "highlights", "_highlights.json"
    )
    highlights_payload = json.loads(
        (run_dir / highlights_rel).read_text(encoding="utf-8")
    )
    assert (
        highlights_payload.get("inputs", {}).get("used_eligibility_fallback") is False
    )
    assert highlights_payload.get("schema_version") == 2
    assert highlights_payload.get("phrase_quality_version") is not None
    theme_labels = {
        str(row.get("label", "")).lower()
        for row in highlights_payload.get("themes", [])
        if isinstance(row, dict)
    }
    assert "a lot" not in theme_labels
    assert "kind of" not in theme_labels
    assert "i mean" not in theme_labels
    assert "of course" not in theme_labels
    assert "need to" not in theme_labels
    assert "going to" not in theme_labels


@pytest.mark.smoke
def test_key_themes_llm_off_zero_client_calls(tmp_path, monkeypatch) -> None:
    """Deterministic themes must work with LLM modules off and zero LLM client calls."""
    from unittest.mock import MagicMock

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

    llm_calls = MagicMock()

    def _tracking_generate(*args, **kwargs):
        llm_calls(*args, **kwargs)
        raise RuntimeError("LLM should not be called for deterministic key themes")

    monkeypatch.setattr(
        "transcriptx.core.llm.llm_client.LLMClient.generate",
        _tracking_generate,
        raising=False,
    )
    try:
        import transcriptx.core.llm.ollama_client as ollama_client

        monkeypatch.setattr(
            ollama_client.OllamaClient,
            "generate",
            _tracking_generate,
            raising=False,
        )
    except Exception:
        pass

    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "tests"
        / "fixtures"
        / "mini_transcript.json"
    )
    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=[
            "tics",
            "insight_eligibility",
            "highlights",
            "summary",
            "insights",
        ],
        persist=False,
    )
    assert result.get("errors") == [], result.get("errors")
    assert llm_calls.call_count == 0

    run_dir = Path(result["output_dir"])
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    summary_rel = _artifact_rel_path_for_module(manifest, "summary", "_summary.json")
    summary_payload = json.loads((run_dir / summary_rel).read_text(encoding="utf-8"))
    bullets = summary_payload.get("key_themes", {}).get("bullets") or []
    banned = {"of course", "need to", "going to", "for example", "we need", "kind of"}
    texts = {str(b.get("text", "")).lower() for b in bullets if isinstance(b, dict)}
    assert texts.isdisjoint(banned)
    # Useful themes: either non-empty or explicitly empty only if no content phrases.
    assert isinstance(bullets, list)
