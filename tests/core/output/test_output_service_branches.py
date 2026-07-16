"""Branch-coverage unit tests for OutputService (offline, mocked renders)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.output.output_service import OutputService, create_output_service
from transcriptx.core.utils.config import TranscriptXConfig, set_config
from transcriptx.core.viz.specs import BarCategoricalSpec


@pytest.fixture
def service(tmp_path: Path) -> OutputService:
    transcript = tmp_path / "call.json"
    transcript.write_text("{}")
    return OutputService(
        str(transcript),
        "sentiment",
        output_dir=str(tmp_path),
        run_id="run-1",
        runtime_flags={},
    )


@pytest.mark.unit
def test_create_output_service_passes_kwargs(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    svc = create_output_service(
        str(transcript),
        "acts",
        output_dir=str(tmp_path),
        run_id="r",
        runtime_flags={"a": 1},
        output_namespace="ns",
        output_version="v1",
    )
    assert isinstance(svc, OutputService)
    assert svc.run_id == "r"
    assert svc.module_name == "acts"


@pytest.mark.unit
def test_record_artifact_outside_transcript_dir(service: OutputService) -> None:
    outside = Path("/tmp/outside_artifact.png")
    service._record_artifact(outside, "png")
    assert service.get_artifacts()[-1]["relative_path"] == outside.as_posix()


@pytest.mark.unit
def test_load_artifact_metadata_valid_invalid_and_missing(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    meta_dir = tmp_path / ".transcriptx"
    meta_dir.mkdir()
    meta_path = meta_dir / "artifacts_meta.json"
    meta_path.write_text(json.dumps({"a.png": {"viz_id": "x"}}))
    svc = OutputService(str(transcript), "sentiment", output_dir=str(tmp_path))
    assert svc._artifact_metadata["a.png"]["viz_id"] == "x"

    meta_path.write_text("not-json")
    svc2 = OutputService(str(transcript), "sentiment", output_dir=str(tmp_path))
    assert svc2._artifact_metadata == {}


@pytest.mark.unit
def test_record_artifact_metadata_merges_and_tolerates_write_failure(
    service: OutputService, tmp_path: Path
) -> None:
    path = Path(service.transcript_dir) / "chart.png"
    path.write_text("x")
    service._record_artifact_metadata(path, {"a": 1})
    service._record_artifact_metadata(path, {"b": 2})
    rel = path.relative_to(Path(service.transcript_dir)).as_posix()
    assert service._artifact_metadata[rel] == {"a": 1, "b": 2}

    with patch(
        "transcriptx.core.output.output_service.write_json",
        side_effect=OSError("fail"),
    ):
        service._record_artifact_metadata(path, {"c": 3})
    # swallow write errors; in-memory may still update before write
    assert "c" in service._artifact_metadata[rel]


@pytest.mark.unit
def test_save_data_formats_and_errors(service: OutputService) -> None:
    with patch("transcriptx.core.output.output_service.save_json") as save_json:
        path = service.save_data({"k": 1}, "x", format_type="json", subdirectory="sub")
    assert "sub" in path
    save_json.assert_called_once()

    with patch("transcriptx.core.output.output_service.save_csv") as save_csv:
        service.save_data([{"a": 1}], "rows", format_type="csv")
        service.save_data({"a": 1}, "dict", format_type="csv")
        service.save_data([1, 2, 3], "list", format_type="csv")
    assert save_csv.call_count == 3

    path = service.save_data({"a": 1}, "info", format_type="txt", subdirectory="notes")
    assert Path(path).exists()
    path2 = service.save_data(["line1", "line2"], "lines", format_type="txt")
    assert "line1" in Path(path2).read_text()

    with pytest.raises(ValueError, match="CSV format requires"):
        service.save_data("bad", "x", format_type="csv")
    with pytest.raises(ValueError, match="Unsupported format"):
        service.save_data({}, "x", format_type="xml")


@pytest.mark.unit
def test_should_skip_speaker_artifact_branches(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    config = TranscriptXConfig()
    config.analysis.exclude_unidentified_from_speaker_charts = True
    set_config(config)

    svc = OutputService(
        str(transcript),
        "sentiment",
        output_dir=str(tmp_path),
        runtime_flags={
            "include_unidentified_speakers": True,
            "named_speaker_keys": {"1"},
        },
    )
    assert svc._should_skip_speaker_artifact("SPEAKER_00") is False

    svc2 = OutputService(
        str(transcript),
        "sentiment",
        output_dir=str(tmp_path),
        runtime_flags={
            "include_unidentified_speakers": False,
            "named_speaker_keys": {"Alice"},
            "speaker_key_aliases": {"alias": "Alice"},
            "ignored_speaker_ids": set(),
        },
    )
    assert svc2._should_skip_speaker_artifact(None) is False
    assert svc2._should_skip_speaker_artifact("Alice") is False
    assert svc2._should_skip_speaker_artifact("Bob") is True
    assert svc2._should_skip_speaker_artifact("alias") is False

    config.analysis.exclude_unidentified_from_speaker_charts = False
    set_config(config)
    svc3 = OutputService(
        str(transcript),
        "sentiment",
        output_dir=str(tmp_path),
        runtime_flags={"include_unidentified_speakers": False},
    )
    assert svc3._should_skip_speaker_artifact("SPEAKER_00") is False


@pytest.mark.unit
def test_resolve_speaker_display_and_json_mapping(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    svc = OutputService(
        str(transcript),
        "sentiment",
        output_dir=str(tmp_path),
        runtime_flags={
            "anonymise_speakers": True,
            "speaker_anonymisation_map": {"Alice": "Speaker 01", "id1": "Speaker 02"},
            "speaker_key_aliases": {"Alice Display": "Alice"},
        },
    )
    assert svc.resolve_speaker_display(None) is None
    assert svc.resolve_speaker_display("Alice") == "Speaker 01"
    assert svc.resolve_speaker_display("Alice Display") == "Speaker 01"
    assert svc.resolve_speaker_display("unknown") == "unknown"

    mapped_row = svc._map_speaker_field({"speaker": "Alice", "n": 1})
    assert mapped_row["speaker"] == "Speaker 01"
    assert svc._map_speaker_field({"n": 1}) == {"n": 1}

    remapped = svc._apply_speaker_mapping_to_json(
        {
            "Alice": {"speaker": "Alice", "v": 1},
            "other": [{"speaker": "Alice"}, "skip"],
        }
    )
    assert "Speaker 01" in remapped
    assert remapped["Speaker 01"]["speaker"] == "Speaker 01"
    assert (
        svc._apply_speaker_mapping_to_json([{"speaker": "Alice"}])[0]["speaker"]
        == "Speaker 01"
    )
    assert svc._apply_speaker_mapping_to_json("plain") == "plain"

    svc_off = OutputService(
        str(transcript),
        "sentiment",
        output_dir=str(tmp_path),
        runtime_flags={"anonymise_speakers": False},
    )
    data = {"Alice": 1}
    assert svc_off._apply_speaker_mapping_to_json(data) is data


@pytest.mark.unit
def test_save_data_skips_unnamed_speaker(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    config = TranscriptXConfig()
    config.analysis.exclude_unidentified_from_speaker_charts = True
    set_config(config)
    svc = OutputService(
        str(transcript),
        "sentiment",
        output_dir=str(tmp_path),
        runtime_flags={
            "include_unidentified_speakers": False,
            "named_speaker_keys": {"Alice"},
        },
    )
    assert svc.save_data({"a": 1}, "x", speaker="Bob") == ""


@pytest.mark.unit
def test_save_text_and_view_html(service: OutputService) -> None:
    path = service.save_text("hello", "readme", ext="md", metadata={"k": 1})
    assert Path(path).exists()
    assert path.endswith(".md")

    path2 = service.save_text("x", "log", ext=".log", subdirectory="logs")
    assert "logs" in path2

    html_path = service.save_view_html(
        "explorer",
        "<html></html>",
        scope="global",
        view_kind="wordcloud_explorer",
        viz_id="wc.view",
        depends_on=["a.json"],
        tags=["t"],
        metadata={"extra": True},
    )
    assert html_path is not None
    assert html_path.exists()

    speaker_path = service.save_view_html(
        "spk",
        "<html>s</html>",
        scope="speaker",
        speaker="Alice Smith",
        view_kind="view",
    )
    assert speaker_path is not None
    assert "Alice_Smith" in str(speaker_path)

    with pytest.raises(ValueError, match="speaker is required"):
        service.save_view_html("bad", "<html></html>", scope="speaker")


@pytest.mark.unit
def test_save_view_html_skips_unnamed_speaker(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    config = TranscriptXConfig()
    config.analysis.exclude_unidentified_from_speaker_charts = True
    set_config(config)
    svc = OutputService(
        str(transcript),
        "sentiment",
        output_dir=str(tmp_path),
        runtime_flags={
            "include_unidentified_speakers": False,
            "named_speaker_keys": set(),
        },
    )
    with patch.object(svc, "_should_skip_speaker_artifact", return_value=True):
        assert (
            svc.save_view_html("x", "<html></html>", scope="speaker", speaker="Bob")
            is None
        )


@pytest.mark.unit
def test_save_chart_spec_speaker_skip_and_dynamic(
    service: OutputService, tmp_path: Path
) -> None:
    config = TranscriptXConfig()
    config.output.dynamic_charts = "on"
    set_config(config)

    with patch.object(service, "_should_skip_speaker_artifact", return_value=True):
        skipped = service.save_chart(
            BarCategoricalSpec(
                viz_id="m.x.speaker",
                module="m",
                name="x",
                scope="speaker",
                speaker="Bob",
                chart_intent="bar_categorical",
                title="t",
                x_label="x",
                y_label="y",
                categories=["a"],
                values=[1],
            )
        )
    assert skipped == {"static": None, "dynamic": None}

    with (
        patch(
            "transcriptx.core.output.output_service.is_plotly_available",
            return_value=True,
        ),
        patch(
            "transcriptx.core.output.output_service.render_mpl",
            return_value=MagicMock(),
        ),
        patch(
            "transcriptx.core.output.output_service.render_plotly",
            return_value=MagicMock(),
        ),
        patch(
            "transcriptx.core.output.output_service.save_static_chart",
            return_value=Path(tmp_path) / "s.png",
        ),
        patch(
            "transcriptx.core.output.output_service.save_dynamic_chart",
            return_value=Path(tmp_path) / "d.html",
        ),
        patch(
            "transcriptx.core.utils.lazy_imports.get_matplotlib_pyplot",
            return_value=MagicMock(),
        ),
    ):
        result = service.save_chart(
            BarCategoricalSpec(
                viz_id="m.y.global",
                module="m",
                name="y",
                scope="global",
                chart_intent="bar_categorical",
                title="t",
                x_label="x",
                y_label="y",
                categories=["a"],
                values=[1],
            )
        )
    assert result["static"] is not None
    assert result["dynamic"] is not None


@pytest.mark.unit
def test_save_chart_spec_requires_speaker(service: OutputService) -> None:
    with pytest.raises(ValueError, match="speaker is required"):
        service.save_chart(
            BarCategoricalSpec(
                viz_id="m.x.speaker",
                module="m",
                name="x",
                scope="speaker",
                speaker=None,
                chart_intent="bar_categorical",
                title="t",
                x_label="x",
                y_label="y",
                categories=["a"],
                values=[1],
            )
        )


@pytest.mark.unit
def test_save_chart_legacy_paths(service: OutputService, tmp_path: Path) -> None:
    config = TranscriptXConfig()
    config.output.dynamic_charts = "auto"
    set_config(config)
    fig = MagicMock()
    dyn = MagicMock()

    with (
        patch(
            "transcriptx.core.output.output_service.is_plotly_available",
            return_value=True,
        ),
        patch(
            "transcriptx.core.output.output_service.save_static_chart",
            return_value=Path(tmp_path) / "s.png",
        ),
        patch(
            "transcriptx.core.output.output_service.save_dynamic_chart",
            return_value=Path(tmp_path) / "d.html",
        ),
        patch(
            "transcriptx.core.utils.lazy_imports.get_matplotlib_pyplot",
            return_value=MagicMock(),
        ),
    ):
        result = service.save_chart(
            chart_id="legacy",
            scope="global",
            static_fig=fig,
            dynamic_fig=dyn,
            title="Legacy",
        )
    assert result["static"] is not None
    assert result["dynamic"] is not None

    with (
        patch(
            "transcriptx.core.output.output_service.save_static_chart",
            return_value=Path(tmp_path) / "sp.png",
        ),
        patch(
            "transcriptx.core.utils.lazy_imports.get_matplotlib_pyplot",
            return_value=MagicMock(),
        ),
    ):
        result2 = service.save_chart(
            chart_id="legacy",
            scope="speaker",
            speaker="Alice",
            static_fig=fig,
            viz_id="m.legacy.speaker",
        )
    assert result2["static"] is not None

    with pytest.raises(ValueError, match="chart_id is required"):
        service.save_chart(static_fig=fig, scope="global")
    with pytest.raises(ValueError, match="scope is required"):
        service.save_chart(chart_id="x", static_fig=fig)
    with pytest.raises(ValueError, match="static_fig is required"):
        service.save_chart(chart_id="x", scope="global")
    with pytest.raises(ValueError, match="speaker is required"):
        service.save_chart(chart_id="x", scope="speaker", static_fig=fig)

    with patch.object(service, "_should_skip_speaker_artifact", return_value=True):
        skipped = service.save_chart(
            chart_id="x", scope="speaker", speaker="Bob", static_fig=fig
        )
    assert skipped == {"static": None, "dynamic": None}


@pytest.mark.unit
def test_should_generate_dynamic_modes(service: OutputService) -> None:
    config = TranscriptXConfig()
    config.output.dynamic_charts = "off"
    set_config(config)
    assert service.should_generate_dynamic() is False

    config.output.dynamic_charts = "on"
    set_config(config)
    with patch(
        "transcriptx.core.output.output_service.is_plotly_available",
        return_value=False,
    ):
        with pytest.raises(RuntimeError, match="Plotly is required"):
            service.should_generate_dynamic()

    with patch(
        "transcriptx.core.output.output_service.is_plotly_available",
        return_value=True,
    ):
        assert service.should_generate_dynamic() is True


@pytest.mark.unit
def test_save_summary_and_record_file(service: OutputService, tmp_path: Path) -> None:
    with patch(
        "transcriptx.core.output.output_service.create_summary_json",
        return_value=str(tmp_path / "summary.json"),
    ):
        path = service.save_summary({"g": 1}, {"Alice": {}}, None)
    assert path.endswith("summary.json")
    assert any(a["artifact_role"] == "summary" for a in service.get_artifacts())

    pdf = tmp_path / "report.pdf"
    pdf.write_text("pdf")
    service.record_file(pdf, "pdf")
    assert service.get_artifacts()[-1]["artifact_type"] == "pdf"
    assert service.get_output_structure() is service.output_structure
