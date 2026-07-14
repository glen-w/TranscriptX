"""Tests for run bootstrap service."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.pipeline.run_bootstrap import RunBootstrapService
from transcriptx.io.import_metadata_sidecar import (
    ManagedTranscriptCategory,
    ValidationResult,
)


def test_load_segments_reads_segments_from_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RunBootstrapService()
    payload = type("Canonical", (), {"segments": [{"speaker": "A", "text": "hi"}]})()
    monkeypatch.setattr(
        "transcriptx.io.transcript_loader.load_canonical_transcript",
        lambda _path: payload,
    )
    assert service.load_segments("/tmp/sample.json") == [{"speaker": "A", "text": "hi"}]


def test_load_segments_reads_segments_from_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RunBootstrapService()
    monkeypatch.setattr(
        "transcriptx.io.transcript_loader.load_canonical_transcript",
        lambda _path: {"segments": [{"speaker": "B", "text": "ok"}]},
    )
    assert service.load_segments("/tmp/sample.json") == [{"speaker": "B", "text": "ok"}]


def test_load_segments_raises_when_payload_has_no_segments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RunBootstrapService()
    monkeypatch.setattr(
        "transcriptx.io.transcript_loader.load_canonical_transcript",
        lambda _path: {"x": 1},
    )
    with pytest.raises(AttributeError, match="does not contain segments"):
        service.load_segments("/tmp/sample.json")


def test_compute_identity_uses_hashers_and_content_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RunBootstrapService()
    segments = [{"speaker": "A", "text": "hello"}]
    monkeypatch.setattr(
        "transcriptx.core.domain.canonical_transcript.CanonicalTranscript.from_segments",
        lambda _segments: type("Canonical", (), {"content_hash": "content-hash"})(),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.canonicalization.compute_transcript_identity_hash",
        lambda _segments: "identity-hash",
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.run_manifest.compute_file_hash",
        lambda _path: "file-hash",
    )
    identity = service.compute_identity("/tmp/input.json", segments)
    assert identity.transcript_identity_hash == "identity-hash"
    assert identity.transcript_content_hash_full == "content-hash"
    assert identity.transcript_file_hash == "file-hash"


def test_validate_managed_noop_when_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    service = RunBootstrapService()
    monkeypatch.setattr(
        "transcriptx.io.import_metadata_sidecar.validate_managed_transcript",
        lambda _path: ValidationResult(
            ok=True,
            category=ManagedTranscriptCategory.ok,
            message="ok",
            warnings=[],
        ),
    )
    service.validate_managed("/tmp/sample.json")


def test_validate_managed_allows_unmanaged_when_env_gate_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RunBootstrapService()
    monkeypatch.setenv("TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS", "1")
    monkeypatch.setattr(
        "transcriptx.io.import_metadata_sidecar.validate_managed_transcript",
        lambda _path: ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.missing_sidecar,
            message="Missing sidecar",
            warnings=[],
        ),
    )
    service.validate_managed("/tmp/sample.json")


def test_validate_managed_raises_when_unmanaged_and_gate_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RunBootstrapService()
    monkeypatch.setenv("TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS", "0")
    monkeypatch.setattr(
        "transcriptx.io.import_metadata_sidecar.validate_managed_transcript",
        lambda _path: ValidationResult(
            ok=False,
            category=ManagedTranscriptCategory.missing_sidecar,
            message="Missing sidecar",
            warnings=[],
        ),
    )
    with pytest.raises(ValueError, match="Cannot register non-managed transcript"):
        service.validate_managed("/tmp/sample.json")


def test_register_uses_canonical_basename_and_returns_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RunBootstrapService()
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_bootstrap.get_canonical_base_name",
        lambda _path: "meeting_file",
    )

    def _fake_register_transcript(**kwargs):
        captured.update(kwargs)
        return "meeting_file__2"

    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.register_transcript",
        _fake_register_transcript,
    )
    out = service.register(
        transcript_path="/tmp/meeting_file.json",
        transcript_key="tk",
        run_id="rid",
    )
    assert out.transcript_key == "tk"
    assert out.run_id == "rid"
    assert out.source_basename == "meeting_file"
    assert out.slug == "meeting_file__2"
    assert captured["source_basename"] == "meeting_file"


def test_register_passes_source_path_to_slug_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RunBootstrapService()
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "transcriptx.core.pipeline.run_bootstrap.get_canonical_base_name",
        lambda _path: "name",
    )

    def _fake_register_transcript(**kwargs):
        captured.update(kwargs)
        return "name"

    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.register_transcript",
        _fake_register_transcript,
    )
    service.register(
        transcript_path="/tmp/path/input.json",
        transcript_key="tk",
        run_id="rid",
    )
    assert captured["source_path"] == "/tmp/path/input.json"


def test_compute_identity_passes_path_object_to_file_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RunBootstrapService()
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        "transcriptx.core.domain.canonical_transcript.CanonicalTranscript.from_segments",
        lambda _segments: type("Canonical", (), {"content_hash": "h"})(),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.canonicalization.compute_transcript_identity_hash",
        lambda _segments: "i",
    )

    def _fake_file_hash(path: Path) -> str:
        seen["path"] = path
        return "f"

    monkeypatch.setattr(
        "transcriptx.core.utils.run_manifest.compute_file_hash", _fake_file_hash
    )
    service.compute_identity("/tmp/one.json", [{"speaker": "A"}])
    assert isinstance(seen["path"], Path)
