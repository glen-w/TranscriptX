import json
from pathlib import Path

from transcriptx.core.analysis.voice.charts_core import VoiceChartsCoreAnalysis
from transcriptx.core.pipeline.pipeline_context import PipelineContext
from transcriptx.core.utils import output_standards as output_standards_module
from transcriptx.core.utils import paths as paths_module


def _write_transcript(path: Path) -> None:
    data = {
        "segments": [
            {"start": 0.0, "end": 2.0, "text": "Hello world", "speaker": "Alice"},
            {"start": 2.5, "end": 4.0, "text": "Hi again", "speaker": "Alice"},
        ]
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def test_voice_charts_core_outputs(tmp_path: Path, monkeypatch) -> None:
    transcript_path = tmp_path / "sample.json"
    _write_transcript(transcript_path)
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(output_dir))
    monkeypatch.setattr(paths_module, "GROUP_OUTPUTS_DIR", str(output_dir / "groups"))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(output_dir))
    monkeypatch.setattr(
        output_standards_module,
        "DIARISED_TRANSCRIPTS_DIR",
        str(tmp_path / "transcripts"),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.output_standards.OUTPUTS_DIR", str(output_dir)
    )

    context = PipelineContext(str(transcript_path), output_dir=str(output_dir))

    # Create a minimal voice_features core JSONL
    core_path = tmp_path / "voice_core.jsonl"
    rows = [
        {
            "segment_id": "seg1",
            "segment_idx": 0,
            "speaker": "Alice",
            "start_s": 0.0,
            "end_s": 2.0,
            "duration_s": 2.0,
            "speech_rate_wps": 1.0,
            "voiced_ratio": 0.8,
        },
        {
            "segment_id": "seg2",
            "segment_idx": 1,
            "speaker": "Alice",
            "start_s": 2.5,
            "end_s": 4.0,
            "duration_s": 1.5,
            "speech_rate_wps": 1.2,
            "voiced_ratio": 0.7,
        },
    ]
    with core_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")

    vad_runs_path = tmp_path / "voice_vad_runs.json"
    vad_runs_path.write_text(
        json.dumps(
            {
                "seg1": {"voiced_runs_s": [0.2, 0.3], "silence_runs_s": [0.1]},
                "seg2": {"voiced_runs_s": [0.4], "silence_runs_s": [0.2, 0.1]},
            }
        ),
        encoding="utf-8",
    )

    locator = {
        "status": "ok",
        "voice_feature_core_path": str(core_path),
        "voice_feature_egemaps_path": None,
        "voice_feature_vad_runs_path": str(vad_runs_path),
    }
    context.store_analysis_result("voice_features", locator)

    pauses_result = {
        "gap_series": [
            {"segment_idx": 0, "gap_seconds": 0.5, "time_start": 2.0, "time_end": 2.5}
        ],
        "per_segment_pause_count": [{"segment_idx": 0, "pause_count": 1}],
    }
    context.store_analysis_result("pauses", pauses_result)

    result = VoiceChartsCoreAnalysis().run_from_context(context)
    assert result.get("status") == "success"

    # voice/v1/data output exists
    data_dir = output_dir / "voice" / "v1" / "data" / "global"
    summary_files = list(data_dir.glob("*_voice_charts_core_summary.json"))
    assert summary_files, "Expected voice_charts_core_summary.json to be written"

    # At least one chart under voice/v1/charts
    charts_dir = output_dir / "voice" / "v1" / "charts"
    chart_files = list(charts_dir.rglob("*.png"))
    assert chart_files, "Expected at least one chart artifact"


def test_voice_charts_core_missing_inputs_skips(tmp_path: Path, monkeypatch) -> None:
    transcript_path = tmp_path / "sample.json"
    _write_transcript(transcript_path)
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(output_dir))
    monkeypatch.setattr(paths_module, "GROUP_OUTPUTS_DIR", str(output_dir / "groups"))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(output_dir))
    monkeypatch.setattr(
        output_standards_module,
        "DIARISED_TRANSCRIPTS_DIR",
        str(tmp_path / "transcripts"),
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.output_standards.OUTPUTS_DIR", str(output_dir)
    )

    context = PipelineContext(str(transcript_path), output_dir=str(output_dir))
    result = VoiceChartsCoreAnalysis().run_from_context(context)
    payload = result.get("payload") or result.get("results") or {}
    assert result.get("status") == "success"
    assert payload.get("status") == "skipped"
    assert payload.get("skipped_reason") in {
        "no_voice_features",
        "missing_optional_deps",
    }
