"""Tests for admitting host originals/ transcripts into the managed library."""

from __future__ import annotations

from pathlib import Path

from transcriptx.io.admit_and_register import AdmitOutcomeKind
from transcriptx.io.admit_originals import (
    admit_originals_file,
    admit_originals_files,
    is_disambiguated_archive_name,
    list_originals_candidates,
    run_admit_originals,
)


def _patch(monkeypatch, transcript_root: Path, outputs: Path) -> None:
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.TRANSCRIPTS_ORIGINALS_DIR",
        transcript_root / "originals",
    )
    monkeypatch.setattr(
        "transcriptx.io.admit_and_register.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_admission.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_admission.TRANSCRIPTS_IMPORTS_DIR",
        transcript_root / "imports",
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR",
        transcript_root / "metadata",
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.INDEX_FILE",
        outputs / ".transcriptx_index.json",
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.OUTPUTS_DIR",
        outputs,
    )
    (transcript_root / "originals").mkdir(parents=True, exist_ok=True)
    (transcript_root / "imports").mkdir(parents=True, exist_ok=True)
    (transcript_root / "metadata").mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)


def test_disambiguated_archive_name() -> None:
    assert is_disambiguated_archive_name("foo (1).json")
    assert is_disambiguated_archive_name("meeting (12).srt")
    assert not is_disambiguated_archive_name("foo.json")
    assert not is_disambiguated_archive_name("foo(1).json")


def test_list_skips_hidden_disambiguated_and_non_transcripts(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "originals"
    folder.mkdir()
    (folder / "keep.srt").write_text("ok", encoding="utf-8")
    (folder / "keep (1).srt").write_text("archive", encoding="utf-8")
    (folder / ".hidden.srt").write_text("no", encoding="utf-8")
    (folder / "notes.txt").write_text("hello", encoding="utf-8")
    (folder / "clip.mp3").write_bytes(b"audio")
    names = {p.name for p in list_originals_candidates(folder)}
    assert names == {"keep.srt", "notes.txt"}


def test_admit_originals_reuses_archive_path(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch(monkeypatch, root, tmp_path / "outputs")
    staging = root / "originals" / "meeting.srt"
    staging.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    outcome = admit_originals_file(staging)
    assert outcome.kind is AdmitOutcomeKind.IMPORTED_AND_REGISTERED
    assert (root / "meeting.json").is_file()
    assert staging.is_file()
    assert not (root / "originals" / "meeting (1).srt").exists()


def test_already_managed_is_skipped(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch(monkeypatch, root, tmp_path / "outputs")
    staging = root / "originals" / "meeting.srt"
    staging.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    first = admit_originals_file(staging)
    assert first.kind is AdmitOutcomeKind.IMPORTED_AND_REGISTERED

    stats = admit_originals_files([staging])
    assert stats.admitted == 0
    assert stats.skipped == 1
    assert stats.failed == 0
    assert stats.outcomes[0][1].kind is AdmitOutcomeKind.ALREADY_MANAGED


def test_run_admit_originals_dry_run_does_not_write(
    monkeypatch, tmp_path: Path
) -> None:
    root = tmp_path / "transcripts"
    _patch(monkeypatch, root, tmp_path / "outputs")
    staging = root / "originals" / "meeting.srt"
    staging.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    rc = run_admit_originals(root / "originals", dry_run=True)
    assert rc == 0
    assert not (root / "meeting.json").exists()


def test_cli_parse_args() -> None:
    from transcriptx.admit_originals import parse_args

    args = parse_args(
        ["--dir", "/tmp/originals", "--transcripts-root", "/tmp/tx", "--dry-run"]
    )
    assert args.directory == Path("/tmp/originals")
    assert args.transcripts_root == Path("/tmp/tx")
    assert args.dry_run is True
    assert args.only is None
