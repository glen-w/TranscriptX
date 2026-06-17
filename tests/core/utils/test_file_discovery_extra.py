"""Additional unit tests for ``core.utils.file_discovery``.

Offline and deterministic (``tmp_path`` + monkeypatch). Extends the existing
``test_file_discovery.py`` to cover discovery-root resolution, the no-``transcripts/``
subdir path, the canonical-validation failure branch, and the recordings-folder
start-path fallbacks.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.core.utils import file_discovery as fd


@pytest.mark.unit
class TestResolveDiscoveryRoot:
    def test_explicit_root_is_returned(self, tmp_path: Path):
        assert fd._resolve_transcript_discovery_root(tmp_path) == Path(tmp_path)

    def test_config_default_folder_when_exists(self, tmp_path: Path, monkeypatch):
        default = tmp_path / "configured"
        default.mkdir()
        monkeypatch.setattr(
            "transcriptx.core.utils.config.get_config",
            lambda: SimpleNamespace(
                output=SimpleNamespace(default_transcript_folder=str(default))
            ),
        )
        assert fd._resolve_transcript_discovery_root(None) == default

    def test_falls_back_to_diarised_dir(self, tmp_path: Path, monkeypatch):
        diarised = tmp_path / "diarised"
        diarised.mkdir()
        monkeypatch.setattr(
            "transcriptx.core.utils.config.get_config",
            lambda: SimpleNamespace(
                output=SimpleNamespace(
                    default_transcript_folder=str(tmp_path / "missing")
                )
            ),
        )
        monkeypatch.setattr(fd, "DIARISED_TRANSCRIPTS_DIR", str(diarised))
        assert fd._resolve_transcript_discovery_root(None) == diarised

    def test_returns_none_when_nothing_exists(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(
            "transcriptx.core.utils.config.get_config",
            lambda: SimpleNamespace(
                output=SimpleNamespace(
                    default_transcript_folder=str(tmp_path / "missing")
                )
            ),
        )
        monkeypatch.setattr(
            fd, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path / "also_missing")
        )
        assert fd._resolve_transcript_discovery_root(None) is None


@pytest.mark.unit
class TestDiscoverAllTranscriptPaths:
    def test_empty_when_root_unresolved(self, monkeypatch):
        monkeypatch.setattr(fd, "_resolve_transcript_discovery_root", lambda root: None)
        assert fd.discover_all_transcript_paths() == []

    def test_searches_root_directly_without_transcripts_subdir(self, tmp_path: Path):
        # No ``transcripts/`` subdir -> search_root is the root itself.
        good = tmp_path / "a.json"
        good.write_text("{}", encoding="utf-8")
        excluded = tmp_path / "x_summary.json"
        excluded.write_text("{}", encoding="utf-8")

        found = fd.discover_all_transcript_paths(tmp_path)
        assert good.resolve() in found
        assert excluded.resolve() not in found

    def test_results_are_sorted_and_deduped(self, tmp_path: Path):
        (tmp_path / "b.json").write_text("{}", encoding="utf-8")
        (tmp_path / "a.json").write_text("{}", encoding="utf-8")
        found = fd.discover_all_transcript_paths(tmp_path)
        assert found == sorted(found, key=lambda p: str(p))


@pytest.mark.unit
class TestDiscoverManagedTranscriptPaths:
    def test_canonical_failure_is_excluded(self, tmp_path: Path, monkeypatch):
        transcripts = tmp_path / "transcripts"
        transcripts.mkdir()
        (transcripts / "t.json").write_text("{}", encoding="utf-8")

        class _Canonical:
            def __init__(self, ok):
                self.ok = ok
                self.category = SimpleNamespace(value="schema_invalid")
                self.message = "bad"

        monkeypatch.setattr(
            "transcriptx.io.canonical_transcript_validation.validate_canonical_transcript",
            lambda p: _Canonical(False),
        )
        # validate_managed_transcript should never be reached for a canonical failure,
        # but patch it defensively so the test cannot hit real validation.
        monkeypatch.setattr(
            "transcriptx.io.import_metadata_sidecar.validate_managed_transcript",
            lambda p: SimpleNamespace(ok=True),
        )

        assert fd.discover_managed_transcript_paths(tmp_path) == []

    def test_managed_failure_with_category_is_excluded(
        self, tmp_path: Path, monkeypatch
    ):
        transcripts = tmp_path / "transcripts"
        transcripts.mkdir()
        (transcripts / "t.json").write_text("{}", encoding="utf-8")

        monkeypatch.setattr(
            "transcriptx.io.canonical_transcript_validation.validate_canonical_transcript",
            lambda p: SimpleNamespace(ok=True),
        )
        monkeypatch.setattr(
            "transcriptx.io.import_metadata_sidecar.validate_managed_transcript",
            lambda p: SimpleNamespace(
                ok=False,
                category=SimpleNamespace(value="unmanaged"),
                message="not in library",
            ),
        )
        assert fd.discover_managed_transcript_paths(tmp_path) == []


@pytest.mark.unit
class TestRecordingsFolderStartPath:
    def test_empty_folders_returns_recordings_dir(self):
        cfg = SimpleNamespace(input=SimpleNamespace(recordings_folders=[]))
        assert fd.get_recordings_folder_start_path(cfg) == Path(fd.RECORDINGS_DIR)

    def test_returns_first_existing_folder(self, tmp_path: Path):
        existing = tmp_path / "recordings"
        existing.mkdir()
        cfg = SimpleNamespace(input=SimpleNamespace(recordings_folders=[str(existing)]))
        assert fd.get_recordings_folder_start_path(cfg) == existing

    def test_walks_up_to_nearest_existing_ancestor(self, tmp_path: Path):
        ancestor = tmp_path / "a"
        ancestor.mkdir()
        missing = (
            ancestor / "b" / "c"
        )  # does not exist; nearest existing is ``ancestor``
        cfg = SimpleNamespace(input=SimpleNamespace(recordings_folders=[str(missing)]))
        assert fd.get_recordings_folder_start_path(cfg) == ancestor

    def test_fallback_when_no_ancestor_exists(self):
        # Use a path whose ancestors do not exist on disk.
        cfg = SimpleNamespace(
            input=SimpleNamespace(recordings_folders=["/nonexistent_root_xyz/a/b"])
        )
        result = fd.get_recordings_folder_start_path(cfg)
        assert result == Path(fd.RECORDINGS_DIR)
