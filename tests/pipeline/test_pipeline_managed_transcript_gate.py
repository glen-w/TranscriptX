"""Tests for pipeline managed transcript gate."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.domain import canonical_transcript as canonical_transcript_module
from transcriptx.core.pipeline import pipeline as pipeline_module
from transcriptx.io.import_metadata_sidecar import (
    ManagedTranscriptCategory,
    ValidationResult,
)


def _patch_minimal_single_run_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline_module, "validate_transcript", lambda _path: None)
    monkeypatch.setattr(
        "transcriptx.io.transcript_loader.load_canonical_transcript",
        lambda _path: SimpleNamespace(
            segments=[{"speaker": "A", "text": "hi", "start": 0.0, "end": 1.0}]
        ),
    )

    def _fake_from_segments(
        cls: type,
        _segments: list,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            content_hash="content-hash",
            schema_version="1.0",
            capabilities=SimpleNamespace(),
        )

    monkeypatch.setattr(
        canonical_transcript_module.CanonicalTranscript,
        "from_segments",
        classmethod(_fake_from_segments),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.canonicalization.compute_transcript_identity_hash",
        lambda _segments: "identity-hash",
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.run_manifest.compute_file_hash",
        lambda _path: "file-hash",
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.register_transcript",
        lambda **_kwargs: "slug",
    )
    monkeypatch.setattr(
        "transcriptx.core.utils._path_core.set_transcript_output_dir",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils._path_core.clear_transcript_output_dir",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.config.persistence.load_draft_override", lambda: None
    )
    monkeypatch.setattr(
        "transcriptx.core.config.resolver.resolve_effective_config",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("stop_after_gate")),
    )


@pytest.mark.unit
def test_single_pipeline_rejects_unmanaged_when_gate_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    transcript_path = tmp_path / "sample.json"
    transcript_path.write_text(
        '{"schema_version":"1.0","source":{"type":"manual","original_path":"x","imported_at":"2026-01-01T00:00:00Z"},"segments":[{"speaker":"A","text":"hi","start":0.0,"end":1.0}]}',
        encoding="utf-8",
    )

    monkeypatch.setenv("TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS", "0")
    monkeypatch.setattr(
        "transcriptx.io.import_metadata_sidecar.validate_managed_transcript",
        lambda _path: ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.missing_sidecar,
            message="Missing import sidecar",
            warnings=[],
        ),
    )
    _patch_minimal_single_run_dependencies(monkeypatch)

    with pytest.raises(ValueError, match="Cannot register non-managed transcript"):
        pipeline_module._run_single_analysis_pipeline(
            transcript_path=str(transcript_path),
            selected_modules=["stats"],
        )


@pytest.mark.unit
def test_single_pipeline_allows_unmanaged_when_gate_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    transcript_path = tmp_path / "sample.json"
    transcript_path.write_text(
        '{"schema_version":"1.0","source":{"type":"manual","original_path":"x","imported_at":"2026-01-01T00:00:00Z"},"segments":[{"speaker":"A","text":"hi","start":0.0,"end":1.0}]}',
        encoding="utf-8",
    )

    monkeypatch.setenv("TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS", "1")
    monkeypatch.setattr(
        "transcriptx.io.import_metadata_sidecar.validate_managed_transcript",
        lambda _path: ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.missing_sidecar,
            message="Missing import sidecar",
            warnings=[],
        ),
    )
    _patch_minimal_single_run_dependencies(monkeypatch)

    with pytest.raises(RuntimeError, match="stop_after_gate"):
        pipeline_module._run_single_analysis_pipeline(
            transcript_path=str(transcript_path),
            selected_modules=["stats"],
        )


@pytest.mark.unit
def test_single_pipeline_sanitizes_activation_keys_when_copying_draft_to_run_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    transcript_path = tmp_path / "sample.json"
    transcript_path.write_text(
        '{"schema_version":"1.0","source":{"type":"manual","original_path":"x","imported_at":"2026-01-01T00:00:00Z"},"segments":[{"speaker":"A","text":"hi","start":0.0,"end":1.0}]}',
        encoding="utf-8",
    )

    monkeypatch.setenv("TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS", "1")
    monkeypatch.setattr(
        "transcriptx.io.import_metadata_sidecar.validate_managed_transcript",
        lambda _path: ValidationResult(
            ok=True,
            category=ManagedTranscriptCategory.ok,
            message="ok",
            warnings=[],
        ),
    )
    _patch_minimal_single_run_dependencies(monkeypatch)

    monkeypatch.setattr(
        "transcriptx.core.config.persistence.load_draft_override",
        lambda: {
            "analysis": {
                "active_acts_profile": "team",
                "semantic_model_name": "model-x",
            },
            "active_workflow_profile": "nightly",
        },
    )

    observed: dict[str, object] = {}

    def _capture_save(run_dir, payload):
        observed["run_dir"] = run_dir
        observed["payload"] = payload

    monkeypatch.setattr(
        "transcriptx.core.config.persistence.save_run_override", _capture_save
    )

    with pytest.raises(RuntimeError, match="stop_after_gate"):
        pipeline_module._run_single_analysis_pipeline(
            transcript_path=str(transcript_path),
            selected_modules=["stats"],
        )

    saved = observed.get("payload")
    assert isinstance(saved, dict)
    assert "active_workflow_profile" not in saved
    assert "active_acts_profile" not in saved.get("analysis", {})
    assert saved["analysis"]["semantic_model_name"] == "model-x"
