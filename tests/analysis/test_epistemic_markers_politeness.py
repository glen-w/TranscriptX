"""Tests for epistemic_markers and politeness analysis modules."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.epistemic_markers import (
    CATEGORIES as EPI_CATEGORIES,
    SCHEMA_ID as EPI_SCHEMA,
    EpistemicMarkersAnalysis,
)
from transcriptx.core.analysis.lexicon_markers.pipeline import run_marker_analysis
from transcriptx.core.analysis.lexicon_markers import derive_epistemic_shares
from transcriptx.core.analysis.politeness import (
    CATEGORIES as POL_CATEGORIES,
    SCHEMA_ID as POL_SCHEMA,
    PolitenessAnalysis,
    _derive_politeness,
)


def _segments() -> list[dict]:
    return [
        {
            "speaker": "Alice",
            "text": "I think we should maybe wait. Definitely not today.",
            "start": 0.0,
            "end": 2.0,
        },
        {
            "speaker": "Bob",
            "text": "Could you please send me the file? Thank you.",
            "start": 2.0,
            "end": 4.0,
        },
        {
            "speaker": "Alice",
            "text": "Tell me the deadline.",
            "start": 4.0,
            "end": 5.0,
        },
    ]


@pytest.mark.unit
def test_epistemic_markers_finds_hedges_and_boosters() -> None:
    result = EpistemicMarkersAnalysis().analyze(_segments())
    assert result["usable"] is True
    assert result["metadata"]["schema_id"] == EPI_SCHEMA
    assert result["global_stats"]["total_marker_hits"] >= 2
    counts = result["global_stats"]["category_counts"]
    assert counts["epistemic_hedge"] >= 1
    assert counts["modal_uncertainty"] >= 1
    assert counts["certainty_booster"] >= 1
    assert result["hits"]
    assert "Alice" in result["speaker_stats"]
    for hit in result["hits"]:
        assert hit["end"] > hit["start"]
        assert hit["module"] == "epistemic_markers"
        assert hit["category"] in EPI_CATEGORIES


@pytest.mark.unit
def test_epistemic_markers_abstains_non_english() -> None:
    segments = [
        {
            "speaker": "Alice",
            "text": "Ich denke vielleicht",
            "language": "de",
            "start": 0.0,
            "end": 1.0,
        }
    ]
    result = EpistemicMarkersAnalysis().analyze(segments)
    assert result["usable"] is False
    assert result["hits"] == []
    assert result["metadata"]["language_status"] == "unsupported"


@pytest.mark.unit
def test_epistemic_markers_empty_transcript() -> None:
    result = EpistemicMarkersAnalysis().analyze([])
    assert result["global_stats"]["total_marker_hits"] == 0


@pytest.mark.unit
def test_epistemic_enabled_categories_filters_hits() -> None:
    result = run_marker_analysis(
        _segments(),
        module="epistemic_markers",
        lexicon_filename="epistemic_markers_en.json",
        categories=EPI_CATEGORIES,
        schema_id=EPI_SCHEMA,
        semantics_version="epistemic_markers_v1",
        enabled_categories=["certainty_booster"],
        min_tokens_for_rates=1,
        derive_fn=derive_epistemic_shares,
    )
    assert result["usable"] is True
    assert result["global_stats"]["category_counts"]["certainty_booster"] >= 1
    assert result["global_stats"]["category_counts"]["epistemic_hedge"] == 0
    assert result["global_stats"]["category_counts"]["modal_uncertainty"] == 0
    assert all(h["category"] == "certainty_booster" for h in result["hits"])


@pytest.mark.unit
def test_epistemic_min_tokens_nulls_rates() -> None:
    result = run_marker_analysis(
        [
            {
                "speaker": "Alice",
                "text": "I think maybe definitely roughly",
            }
        ],
        module="epistemic_markers",
        lexicon_filename="epistemic_markers_en.json",
        categories=EPI_CATEGORIES,
        schema_id=EPI_SCHEMA,
        semantics_version="epistemic_markers_v1",
        enabled_categories=None,
        min_tokens_for_rates=10_000,
        derive_fn=derive_epistemic_shares,
    )
    assert result["global_stats"]["total_marker_hits"] >= 1
    assert result["global_stats"]["hits_per_100_tokens"] is None
    rates = result["global_stats"]["category_rates_per_100_tokens"]
    assert all(v is None for v in rates.values())


@pytest.mark.unit
def test_epistemic_write_csv(tmp_path: Path) -> None:
    module = EpistemicMarkersAnalysis()
    results = module.analyze(_segments())
    csv_path = tmp_path / "epi.csv"
    module._write_csv(results, csv_path)
    text = csv_path.read_text(encoding="utf-8")
    assert "scope" in text
    assert "hedge_share" in text
    assert "global" in text


@pytest.mark.unit
def test_politeness_softener_vs_directive() -> None:
    result = PolitenessAnalysis().analyze(_segments())
    assert result["usable"] is True
    assert result["metadata"]["schema_id"] == POL_SCHEMA
    counts = result["global_stats"]["category_counts"]
    assert counts["request_softener"] >= 1
    assert counts["gratitude"] >= 1
    assert counts["bare_directive"] >= 1
    ratio = result["global_stats"]["soft_request_ratio"]
    assert ratio is not None
    assert 0.0 < ratio < 1.0
    for hit in result["hits"]:
        assert hit["category"] in POL_CATEGORIES
        assert hit["module"] == "politeness"


@pytest.mark.unit
def test_politeness_modal_not_in_epistemic_hits() -> None:
    """could you is politeness-owned; must not appear as epistemic."""
    epi = EpistemicMarkersAnalysis().analyze(_segments())
    surfaces = {h["surface"].casefold() for h in epi["hits"]}
    assert "could you" not in surfaces
    pol = PolitenessAnalysis().analyze(_segments())
    pol_surfaces = {h["surface"].casefold() for h in pol["hits"]}
    assert any("could you" in s for s in pol_surfaces)


@pytest.mark.unit
def test_politeness_abstains_non_english() -> None:
    segments = [{"speaker": "Alice", "text": "Merci beaucoup", "language": "fr"}]
    result = PolitenessAnalysis().analyze(segments)
    assert result["usable"] is False
    assert result["metadata"]["language_status"] == "unsupported"


@pytest.mark.unit
def test_politeness_enabled_categories_filters() -> None:
    result = run_marker_analysis(
        _segments(),
        module="politeness",
        lexicon_filename="politeness_en.json",
        categories=POL_CATEGORIES,
        schema_id=POL_SCHEMA,
        semantics_version="politeness_v1",
        enabled_categories=["gratitude"],
        min_tokens_for_rates=1,
        derive_fn=_derive_politeness,
    )
    assert result["global_stats"]["category_counts"]["gratitude"] >= 1
    assert result["global_stats"]["category_counts"]["request_softener"] == 0
    assert all(h["category"] == "gratitude" for h in result["hits"])


@pytest.mark.unit
def test_politeness_write_csv(tmp_path: Path) -> None:
    module = PolitenessAnalysis()
    results = module.analyze(_segments())
    csv_path = tmp_path / "pol.csv"
    module._write_csv(results, csv_path)
    text = csv_path.read_text(encoding="utf-8")
    assert "soft_request_ratio" in text
    assert "global" in text


@pytest.mark.unit
def test_save_results_writes_json(tmp_path: Path) -> None:
    module = EpistemicMarkersAnalysis()
    results = module.analyze(_segments())

    class _Structure:
        global_data_dir = tmp_path

    svc = MagicMock()
    svc.base_name = "demo"
    svc.get_output_structure.return_value = _Structure()
    svc.save_data = MagicMock()
    svc.record_file = MagicMock()
    svc.save_summary = MagicMock()
    svc.save_chart = MagicMock()

    module._save_results(results, svc)
    assert svc.save_data.called
    payload = svc.save_data.call_args.args[0]
    assert payload["schema_id"] == EPI_SCHEMA
    assert "hits" in payload
    assert (tmp_path / "demo_epistemic_markers.csv").exists()
