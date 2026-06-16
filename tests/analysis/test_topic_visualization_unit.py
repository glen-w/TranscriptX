from __future__ import annotations

import pytest

from transcriptx.core.analysis.topic_modeling import visualization as viz
from transcriptx.core.analysis.topic_modeling.visualization import (
    _build_topic_label_map,
    _row_weight,
    create_diagnostic_plots,
    create_discourse_analysis_charts,
    create_enhanced_global_heatmaps,
    create_enhanced_html_report,
    create_expected_topic_proportions_bar,
    create_html_report,
    create_speaker_topic_engagement_heatmap,
    create_topic_evolution_timeline,
    format_topic_display,
)
from transcriptx.core.viz.specs import BarCategoricalSpec, HeatmapMatrixSpec

pytestmark = pytest.mark.unit


class _DummyOutputService:
    def __init__(self) -> None:
        self.specs: list[object] = []

    def save_chart(self, *args, **kwargs):
        self.specs.append(args[0] if args else kwargs)
        return {"static": "/tmp/fake.png", "chart_type": kwargs.get("chart_type")}


def _topics() -> list[dict]:
    return [
        {
            "topic_id": 0,
            "label": "Planning",
            "words": ["plan", "risk"],
            "weights": [0.7, 0.3],
            "coherence": 0.6,
        },
        {
            "topic_id": 1,
            "label": "Delivery",
            "words": ["ship", "test"],
            "weights": [0.4, 0.2],
            "coherence": 0.5,
        },
    ]


def test_topic_labels_and_weights_are_stable() -> None:
    labels = _build_topic_label_map(
        [
            {"topic_id": "0", "label": "  Climate finance and accountability  "},
            {"topic_id": "not-int", "label": "ignored"},
            {"topic_id": 1, "label": ""},
        ]
    )

    assert labels == {0: "Climate finance and accountability"}
    assert format_topic_display(0, labels, max_label_len=16) == (
        "T0 \u2013 Climate finance\u2026"
    )
    assert format_topic_display(1, labels) == "T1"
    assert format_topic_display(0, labels, include_label=False) == "T0"
    assert _row_weight({"weight": "2.5"}) == 2.5
    assert _row_weight({"weight": "-1", "row_weight": "bad"}) == 1.0


def test_diagnostic_and_discourse_charts_save_with_output_service() -> None:
    output_service = _DummyOutputService()

    diagnostic_paths = create_diagnostic_plots(
        {
            "k_values": [2, 3],
            "held_out_likelihood": [-10, -8],
            "coherence_scores": [0.2, 0.4],
            "silhouette_scores": [0.1, 0.3],
            "residuals": [4, 2],
        },
        algorithm="lda",
        base_name="fixture",
        output_structure={},
        output_service=output_service,
    )
    discourse_paths = create_discourse_analysis_charts(
        {
            "topic_prevalence": {"intro": {0: 0.7, 1: 0.3}},
            "topic_confidence": {"intro": {0: 0.9, 1: 0.5}},
            "discourse_summary": {
                "intro": {
                    "total_segments": 3,
                    "topic_diversity": 2,
                    "avg_confidence": 0.8,
                }
            },
        },
        base_name="fixture",
        output_structure={},
        output_service=output_service,
    )

    assert diagnostic_paths == ["/tmp/fake.png"]
    assert discourse_paths == ["/tmp/fake.png"]
    assert output_service.specs[0]["chart_id"] == "lda_diagnostic_plots"
    assert output_service.specs[1]["chart_id"] == "discourse_analysis"


def test_enhanced_heatmaps_and_speaker_charts_emit_specs(monkeypatch) -> None:
    saved_speaker_payloads: list[tuple] = []
    monkeypatch.setattr(
        viz,
        "save_speaker_data",
        lambda *args, **kwargs: saved_speaker_payloads.append((args, kwargs)),
    )
    output_service = _DummyOutputService()
    html_imgs: list[str] = []

    create_enhanced_global_heatmaps(
        {"topics": _topics()},
        {"topics": _topics()},
        base_name="fixture",
        output_structure={},
        html_imgs=html_imgs,
        output_service=output_service,
    )
    viz.create_speaker_charts(
        {"topics": _topics(), "doc_topics": [[0.8, 0.2], [0.1, 0.9]]},
        {"doc_topics": [[0.2, 0.8], [0.6, 0.4]]},
        speaker_labels=["Alice", "SPEAKER_00"],
        base_name="fixture",
        output_structure={},
        html_imgs=html_imgs,
        output_service=output_service,
    )

    assert len(output_service.specs) == 3
    assert all(
        isinstance(spec, (HeatmapMatrixSpec, BarCategoricalSpec))
        for spec in output_service.specs
    )
    assert html_imgs == ["/tmp/fake.png", "/tmp/fake.png", "/tmp/fake.png"]
    assert saved_speaker_payloads


def test_timeline_engagement_and_expected_topic_specs() -> None:
    output_service = _DummyOutputService()
    topics = [
        {"topic_id": 0, "label": "Planning"},
        {"topic_id": 1, "label": "Delivery"},
    ]
    docs = [
        {"time": 0.0, "speaker": "Alice", "dominant_topic": 0, "weight": 2},
        {"time": 5.0, "speaker": "Alice / Bob", "dominant_topic": 1},
        {"time": 10.0, "speaker": "", "dominant_topic": None},
    ]

    assert (
        create_topic_evolution_timeline(
            docs,
            base_name="fixture",
            output_structure={},
            lda_topics=topics,
            output_service=output_service,
        )
        == "/tmp/fake.png"
    )
    assert (
        create_speaker_topic_engagement_heatmap(
            docs,
            base_name="fixture",
            output_structure={},
            lda_topics=topics,
            output_service=output_service,
        )
        == "/tmp/fake.png"
    )
    assert (
        create_expected_topic_proportions_bar(
            docs,
            topics,
            base_name="fixture",
            output_structure={},
            output_service=output_service,
        )
        == "/tmp/fake.png"
    )

    assert output_service.specs[0].name == "topic_evolution_timeline"
    assert output_service.specs[1].name == "speaker_topic_engagement_heatmap"
    assert output_service.specs[2].name == "expected_topic_proportions"


def test_html_report_builders_write_only_existing_charts(tmp_path) -> None:
    chart_path = tmp_path / "chart.png"
    chart_path.write_text("png", encoding="utf-8")
    simple_report = tmp_path / "simple.html"
    enhanced_report = tmp_path / "enhanced.html"
    lda_results = {
        "optimal_k": 1,
        "doc_topic_data": [{"speaker": "Alice"}],
        "topics": [
            {
                "topic_id": 0,
                "label": "Planning",
                "coherence": 0.75,
                "words": ["plan", "risk", "ship"],
            }
        ],
    }
    nmf_results = {
        "optimal_k": 1,
        "topics": [
            {
                "topic_id": 0,
                "label": "Delivery",
                "coherence": 0.5,
                "words": ["ship", "test", "done"],
            }
        ],
    }

    create_html_report(simple_report, [str(chart_path), str(tmp_path / "missing.png")])
    create_enhanced_html_report(
        enhanced_report,
        [str(chart_path), str(tmp_path / "missing.png")],
        lda_results,
        nmf_results,
        {
            "discourse_summary": {
                "intro": {
                    "total_segments": 1,
                    "topic_diversity": 1,
                    "avg_confidence": 0.8,
                }
            }
        },
    )

    assert "chart.png" in simple_report.read_text(encoding="utf-8")
    enhanced_html = enhanced_report.read_text(encoding="utf-8")
    assert "Enhanced Topic Modeling Report" in enhanced_html
    assert "Planning" in enhanced_html
    assert "missing.png" not in enhanced_html


def test_plotly_helpers_return_false_when_plotly_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(viz, "_get_plotly", lambda: None)

    assert (
        viz.create_plotly_heatmap([[1]], ["word"], ["T0"], "Title", tmp_path / "h.html")
        is False
    )
    assert (
        viz.create_plotly_speaker_chart(
            {"lda": [0], "nmf": [1]}, "Alice", tmp_path / "s.html"
        )
        is False
    )
