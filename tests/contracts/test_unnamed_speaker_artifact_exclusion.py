"""
Contract: unidentified speakers must not appear in generated per-speaker
artifacts (charts / speaker-scoped files) when exclusion is enabled.

See docs/contracts/output-contract-v1.md. Global-scope "All Speakers" bar
charts must filter categories in the module (OutputService only gates
scope='speaker' artifacts).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis import lexical_diversity as ld
from transcriptx.core.output.output_service import OutputService
from transcriptx.core.utils.config import TranscriptXConfig, set_config
from transcriptx.core.utils.understandability import (
    save_understandability_csv,
    save_understandability_json,
)
from transcriptx.core.viz.specs import BarCategoricalSpec
from transcriptx.utils.text_utils import (
    is_eligible_named_speaker,
    is_named_speaker,
    is_turn_taking_speaker_label,
)


@pytest.mark.contract
@pytest.mark.unit
def test_named_speaker_predicates_split_turn_taking_from_display() -> None:
    assert is_turn_taking_speaker_label("SPEAKER_03") is True
    assert is_named_speaker("SPEAKER_03") is False
    assert is_named_speaker("Speaker 03") is False
    assert is_named_speaker("Ana") is True
    assert is_eligible_named_speaker("SPEAKER_03", "SPEAKER_03") is False
    assert is_eligible_named_speaker("Ana", "SPEAKER_00") is True
    assert (
        is_eligible_named_speaker("SPEAKER_03", "SPEAKER_03", allow_unnamed=True)
        is True
    )


@pytest.mark.contract
@pytest.mark.unit
def test_output_service_skips_speaker_scoped_diarization_label(
    tmp_path: Path,
) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    config = TranscriptXConfig()
    config.analysis.exclude_unidentified_from_speaker_charts = True
    set_config(config)

    service = OutputService(
        str(transcript),
        "sentiment",
        output_dir=str(tmp_path / "out"),
        runtime_flags={"include_unidentified_speakers": False},
    )
    assert service._should_skip_speaker_artifact("SPEAKER_00") is True
    assert service._should_skip_speaker_artifact("Alice") is False

    skipped = service.save_chart(
        BarCategoricalSpec(
            viz_id="sentiment.demo.speaker",
            module="sentiment",
            name="demo",
            scope="speaker",
            speaker="SPEAKER_00",
            chart_intent="bar_categorical",
            title="demo",
            x_label="x",
            y_label="y",
            categories=["a"],
            values=[1.0],
        )
    )
    assert skipped == {"static": None, "dynamic": None}


@pytest.mark.contract
@pytest.mark.unit
def test_output_service_includes_diarization_label_when_ungated(
    tmp_path: Path,
) -> None:
    """When allow_unnamed forces include_unidentified, SPEAKER_* artifacts emit."""
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    config = TranscriptXConfig()
    config.analysis.exclude_unidentified_from_speaker_charts = True
    set_config(config)

    service = OutputService(
        str(transcript),
        "sentiment",
        output_dir=str(tmp_path / "out"),
        runtime_flags={
            "include_unidentified_speakers": True,
            "allow_unnamed_speakers": True,
        },
    )
    assert service._should_skip_speaker_artifact("SPEAKER_00") is False


@pytest.mark.contract
@pytest.mark.unit
def test_output_service_global_chart_bypass_speaker_skip_gate(
    tmp_path: Path,
) -> None:
    """scope=global is not gated by speaker identity; modules must filter bars."""
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    config = TranscriptXConfig()
    config.analysis.exclude_unidentified_from_speaker_charts = True
    set_config(config)
    service = OutputService(
        str(transcript),
        "lexical_diversity",
        output_dir=str(tmp_path / "out"),
    )
    # Unnamed labels are skipped only for speaker-scoped artifacts.
    assert service._should_skip_speaker_artifact("SPEAKER_03") is True

    seen: list[list[str]] = []

    def _fake_save_static(fig, path, **_kwargs):
        del fig
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"png")
        return Path(path)

    with (
        patch(
            "transcriptx.core.output.output_service.render_mpl",
            return_value=MagicMock(),
        ),
        patch(
            "transcriptx.core.output.output_service.save_static_chart",
            side_effect=_fake_save_static,
        ),
        patch(
            "transcriptx.core.utils.lazy_imports.get_matplotlib_pyplot",
            return_value=MagicMock(),
        ),
    ):
        spec = BarCategoricalSpec(
            viz_id="lexical_diversity.hapax_rate.speaker",
            module="lexical_diversity",
            name="lexical-hapax-rate",
            scope="global",
            chart_intent="bar_categorical",
            title="t",
            x_label="Speaker",
            y_label="hapax_rate",
            categories=["Ana", "SPEAKER_03"],
            values=[0.5, 0.8],
        )
        seen.append(list(spec.categories))
        result = service.save_chart(spec)
    assert result["static"] is not None
    assert seen[0] == ["Ana", "SPEAKER_03"]


@pytest.mark.contract
@pytest.mark.unit
def test_lexical_diversity_generated_charts_exclude_unnamed() -> None:
    class _Out:
        def __init__(self) -> None:
            self.specs: list[BarCategoricalSpec] = []

        def save_chart(self, spec, **_kwargs):
            self.specs.append(spec)

    out = _Out()
    ld._plot_lexical_diversity_charts(
        {
            "speaker_stats": {
                "Ana": {"ttr": 0.5, "mtld": 10.0, "hapax_rate": 0.53},
                "Glen": {"ttr": 0.48, "mtld": 9.0, "hapax_rate": 0.52},
                "SPEAKER_03": {"ttr": 0.9, "mtld": 2.0, "hapax_rate": 0.8},
                "Unknown": {"ttr": 0.7, "mtld": 3.0, "hapax_rate": 0.6},
            }
        },
        out,
    )
    assert out.specs
    for spec in out.specs:
        assert all(is_named_speaker(c) for c in spec.categories)
        assert "SPEAKER_03" not in spec.categories
        assert "Unknown" not in spec.categories


@pytest.mark.contract
@pytest.mark.unit
def test_lexical_diversity_json_may_retain_unnamed_for_completeness() -> None:
    module = ld.LexicalDiversityAnalysis()
    result = module.analyze(
        [
            {"speaker": "Ana", "text": "hello world again", "start": 0.0, "end": 1.0},
            {
                "speaker": "SPEAKER_03",
                "text": "unique rare words only once",
                "start": 1.0,
                "end": 2.0,
            },
        ]
    )
    assert "SPEAKER_03" in result["speaker_stats"]
    assert "Ana" in result["speaker_stats"]


@pytest.mark.contract
@pytest.mark.unit
def test_understandability_persisted_artifacts_exclude_unnamed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from transcriptx.core.utils.output_standards import create_standard_output_structure

    outputs = tmp_path / "outputs"
    monkeypatch.setattr("transcriptx.core.utils.output_standards.OUTPUTS_DIR", outputs)
    out = create_standard_output_structure(str(outputs / "mini"), "understandability")
    out.global_data_dir.mkdir(parents=True, exist_ok=True)
    out.speaker_data_dir.mkdir(parents=True, exist_ok=True)

    scores = {
        "Alice": {
            "flesch_reading_ease": 70.0,
            "gunning_fog_index": 8.0,
            "smog_index": 7.0,
            "automated_readability_index": 6.0,
            "avg_sentence_length": 10.0,
            "lexical_density": 0.5,
            "word_count": 12,
            "sentence_count": 2,
        },
        "SPEAKER_00": {
            "flesch_reading_ease": 60.0,
            "gunning_fog_index": 9.0,
            "smog_index": 8.0,
            "automated_readability_index": 7.0,
            "avg_sentence_length": 11.0,
            "lexical_density": 0.4,
            "word_count": 8,
            "sentence_count": 1,
        },
    }

    with patch("transcriptx.core.utils.understandability.notify_user"):
        save_understandability_csv(scores, out, "mini")
        save_understandability_json(scores, out, "mini")

    csv_body = (out.global_data_dir / "mini_understandability.csv").read_text(
        encoding="utf-8"
    )
    json_body = (out.global_data_dir / "mini_understandability.json").read_text(
        encoding="utf-8"
    )
    assert "Alice" in csv_body and "SPEAKER_00" not in csv_body
    assert "Alice" in json_body and "SPEAKER_00" not in json_body
    assert (out.speaker_data_dir / "mini_understandability_Alice.csv").exists()
    assert not list(out.speaker_data_dir.glob("*SPEAKER*"))
