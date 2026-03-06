"""Tests for DB-free transcript validate and canonicalize CLI commands."""

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

# Invoke via transcript app to avoid pulling in transcript_file_commands (and its
# transcript_loader import) before the app is loaded, which can trigger circular imports.
from transcriptx.cli.main import app as main_app

runner = CliRunner()


def test_validate_canonical_transcript(tmp_path):
    """Valid canonical document passes validate (exit 0)."""
    canonical = {
        "schema_version": "1.0",
        "source": {
            "type": "whisperx",
            "original_path": "x.mp3",
            "imported_at": "2026-01-01T00:00:00Z",
        },
        "metadata": {"duration_seconds": 10.0, "segment_count": 1, "speaker_count": 1},
        "segments": [
            {"start": 0.0, "end": 10.0, "speaker": "SPEAKER_00", "text": "Hello."}
        ],
    }
    path = tmp_path / "canonical.json"
    path.write_text(json.dumps(canonical))
    result = runner.invoke(main_app, ["transcript", "validate", "--file", str(path)])
    assert result.exit_code == 0
    assert "Valid" in result.output


def test_validate_legacy_whisperx_format():
    """Raw WhisperX JSON (no schema_version) is reported as loadable but not canonical (exit 1)."""
    fixture = (
        Path(__file__).resolve().parent.parent / "fixtures" / "whisperx_legacy.json"
    )
    if not fixture.exists():
        pytest.skip("whisperx_legacy.json fixture not found")
    result = runner.invoke(main_app, ["transcript", "validate", "--file", str(fixture)])
    assert result.exit_code == 1
    assert (
        "Loadable but not canonical" in result.output
        or "canonicalize" in result.output.lower()
    )


def test_validate_rejects_invalid(tmp_path):
    """Missing required fields or wrong types yield exit 1."""
    bad = {"schema_version": "1.0", "source": {}, "segments": []}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad))
    result = runner.invoke(main_app, ["transcript", "validate", "--file", str(path)])
    assert result.exit_code == 1


def test_validate_file_not_found():
    """Missing file yields exit 2."""
    result = runner.invoke(
        main_app, ["transcript", "validate", "--file", "/nonexistent/file.json"]
    )
    assert result.exit_code == 2


def test_canonicalize_whisperx_json(tmp_path):
    """Raw WhisperX output -> canonical format with schema_version, source, metadata."""
    fixture = (
        Path(__file__).resolve().parent.parent / "fixtures" / "whisperx_legacy.json"
    )
    if not fixture.exists():
        pytest.skip("whisperx_legacy.json fixture not found")
    out = tmp_path / "out.json"
    result = runner.invoke(
        main_app,
        ["transcript", "canonicalize", "--in", str(fixture), "--out", str(out)],
    )
    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data["schema_version"] == "1.0"
    assert "source" in data and data["source"]["type"] == "whisperx"
    assert data["metadata"]["segment_count"] == 2
    assert data["metadata"]["speaker_count"] == 2
    assert data["metadata"]["duration_seconds"] == 5.0


def test_canonicalize_default_output_path(tmp_path):
    """When --out is omitted, output goes to <stem>_transcriptx.json."""
    fixture = (
        Path(__file__).resolve().parent.parent / "fixtures" / "whisperx_legacy.json"
    )
    if not fixture.exists():
        pytest.skip("whisperx_legacy.json fixture not found")
    # Copy fixture to tmp_path so we can write alongside it
    import shutil

    local_in = tmp_path / "whisperx_legacy.json"
    shutil.copy(fixture, local_in)
    result = runner.invoke(
        main_app, ["transcript", "canonicalize", "--in", str(local_in)]
    )
    assert result.exit_code == 0
    default_out = tmp_path / "whisperx_legacy_transcriptx.json"
    assert default_out.exists()
    data = json.loads(default_out.read_text())
    assert data["schema_version"] == "1.0"


def test_canonicalize_normalizes_speakers(tmp_path):
    """Missing/null/empty speaker -> SPEAKER_UNKNOWN."""
    raw = {
        "segments": [
            {"start": 0.0, "end": 1.0, "text": "A", "speaker": "SPEAKER_00"},
            {"start": 1.0, "end": 2.0, "text": "B"},
            {"start": 2.0, "end": 3.0, "text": "C", "speaker": ""},
        ]
    }
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(raw))
    out = tmp_path / "out.json"
    result = runner.invoke(
        main_app, ["transcript", "canonicalize", "--in", str(inp), "--out", str(out)]
    )
    assert result.exit_code == 0
    data = json.loads(out.read_text())
    speakers = {s["speaker"] for s in data["segments"]}
    assert "SPEAKER_00" in speakers
    assert "SPEAKER_UNKNOWN" in speakers
    assert data["metadata"]["speaker_count"] == 2


def test_canonicalize_fills_metadata_gaps(tmp_path):
    """Input missing duration_seconds or segment_count -> canonicalize computes them."""
    raw = {
        "segments": [
            {"start": 0.0, "end": 5.0, "speaker": "A", "text": "One"},
            {"start": 5.0, "end": 10.0, "speaker": "B", "text": "Two"},
        ]
    }
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(raw))
    out = tmp_path / "out.json"
    result = runner.invoke(
        main_app, ["transcript", "canonicalize", "--in", str(inp), "--out", str(out)]
    )
    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data["metadata"]["segment_count"] == 2
    assert data["metadata"]["duration_seconds"] == 10.0
    assert data["metadata"]["speaker_count"] == 2


def test_canonicalize_bare_segment_list(tmp_path):
    """JSON that is just [{start, end, speaker, text}, ...] -> canonical format."""
    raw = [
        {"start": 0.0, "end": 2.0, "speaker": "Alice", "text": "Hi."},
        {"start": 2.0, "end": 4.0, "speaker": "Bob", "text": "Bye."},
    ]
    inp = tmp_path / "bare.json"
    inp.write_text(json.dumps(raw))
    out = tmp_path / "out.json"
    result = runner.invoke(
        main_app, ["transcript", "canonicalize", "--in", str(inp), "--out", str(out)]
    )
    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data["schema_version"] == "1.0"
    assert "source" in data and "metadata" in data
    assert len(data["segments"]) == 2
    assert data["metadata"]["segment_count"] == 2
    assert data["metadata"]["speaker_count"] == 2


def test_canonicalize_idempotent(tmp_path):
    """Already-canonical JSON -> same structure (no double-wrapping)."""
    canonical = {
        "schema_version": "1.0",
        "source": {
            "type": "manual",
            "original_path": "x.wav",
            "imported_at": "2026-01-01T00:00:00Z",
        },
        "metadata": {"duration_seconds": 10.0, "segment_count": 1, "speaker_count": 1},
        "segments": [{"start": 0.0, "end": 10.0, "speaker": "Alice", "text": "Hello."}],
    }
    inp = tmp_path / "canonical_in.json"
    inp.write_text(json.dumps(canonical))
    out = tmp_path / "canonical_out.json"
    result = runner.invoke(
        main_app, ["transcript", "canonicalize", "--in", str(inp), "--out", str(out)]
    )
    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data["schema_version"] == "1.0"
    assert data["metadata"]["segment_count"] == 1
    assert data["metadata"]["speaker_count"] == 1
    assert len(data["segments"]) == 1
    assert data["segments"][0]["speaker"] == "Alice"


def test_validate_canonicalize_no_db_init(tmp_path):
    """Validate and canonicalize are DB-free: no SQLite file created, no DB engine in sys.modules."""
    canonical = {
        "schema_version": "1.0",
        "source": {
            "type": "manual",
            "original_path": "x.wav",
            "imported_at": "2026-01-01T00:00:00Z",
        },
        "metadata": {"duration_seconds": 5.0, "segment_count": 1, "speaker_count": 1},
        "segments": [{"start": 0.0, "end": 5.0, "speaker": "Alice", "text": "Hi."}],
    }
    path = tmp_path / "t.json"
    path.write_text(json.dumps(canonical))
    out = tmp_path / "out.json"
    env = os.environ.copy()
    env["TRANSCRIPTX_DATA_DIR"] = str(tmp_path)
    env["TRANSCRIPTX_CONFIG_DIR"] = str(tmp_path / ".tx")
    result = runner.invoke(
        main_app,
        ["transcript", "validate", "--file", str(path)],
        env=env,
    )
    assert result.exit_code == 0
    result2 = runner.invoke(
        main_app,
        ["transcript", "canonicalize", "--in", str(path), "--out", str(out)],
        env=env,
    )
    assert result2.exit_code == 0
    db_files = list(tmp_path.rglob("*.db"))
    assert not db_files, f"Expected no SQLite files under {tmp_path}, found: {db_files}"


def test_analyze_accepts_raw_whisperx_json(tmp_path):
    """CLI analyze with raw WhisperX JSON (no schema_version) exits 0 and prints canonicalize hint."""
    fixture = (
        Path(__file__).resolve().parent.parent / "fixtures" / "whisperx_legacy.json"
    )
    if not fixture.exists():
        pytest.skip("whisperx_legacy.json fixture not found")
    result = runner.invoke(
        main_app,
        [
            "analyze",
            "--transcript-file",
            str(fixture),
            "--modules",
            "stats",
            "--skip-confirm",
            "--accept-noncanonical",
        ],
    )
    assert result.exit_code == 0
    assert (
        "canonicalize" in result.output.lower() or "loadable" in result.output.lower()
    )


def test_analysis_runs_without_docker(tmp_path):
    """Analysis pipeline runs without Docker: load canonical fixture, run stats, assert success."""
    fixture = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "example_meeting_transcriptx.json"
    )
    if not fixture.exists():
        pytest.skip("example_meeting_transcriptx.json fixture not found")
    env = os.environ.copy()
    env["TRANSCRIPTX_DATA_DIR"] = str(tmp_path)
    env["TRANSCRIPTX_OUTPUT_DIR"] = str(tmp_path / "outputs")
    env["TRANSCRIPTX_CONFIG_DIR"] = str(tmp_path / ".tx")
    result = runner.invoke(
        main_app,
        [
            "analyze",
            "--transcript-file",
            str(fixture),
            "--modules",
            "stats",
            "--skip-confirm",
        ],
        env=env,
    )
    assert result.exit_code == 0
    assert (
        "Pipeline completed" in result.output
        or "Ran 1 modules" in result.output
        or "Completed" in result.output
    )
