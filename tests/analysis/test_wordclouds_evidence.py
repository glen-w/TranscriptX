"""Evidence quality floor for wordcloud PreRenderedFigureSpec writers."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.wordclouds.output_bridge import _wordcloud_chart_spec
from transcriptx.core.viz.specs import PreRenderedFigureSpec

pytestmark = pytest.mark.unit


def test_wordcloud_chart_spec_includes_top_term_evidence() -> None:
    fig = object()
    spec = _wordcloud_chart_spec(
        fig,
        filename="basic",
        scope="global",
        speaker=None,
        title="Basic",
        viz_id="wordclouds.basic.global",
        frequencies={"alpha": 3.0, "beta": 1.0, "gamma": 2.0},
        module="wordclouds",
    )
    assert isinstance(spec, PreRenderedFigureSpec)
    assert spec.labels == ["alpha", "gamma", "beta"]
    assert spec.values == [3.0, 2.0, 1.0]
    assert "source:wordcloud_frequencies" in spec.transformations


def test_wordcloud_chart_spec_empty_frequencies_omits_term_evidence() -> None:
    spec = _wordcloud_chart_spec(
        object(),
        filename="empty",
        scope="global",
        speaker=None,
        title=None,
        viz_id=None,
        frequencies={},
        module="wordclouds",
    )
    assert spec.labels == []
    assert spec.values == []
    assert spec.transformations == ()
