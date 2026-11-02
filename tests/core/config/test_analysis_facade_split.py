"""Analysis config facade re-exports slice dataclasses (1.9 file split)."""

from __future__ import annotations

import pytest

from transcriptx.core.utils.config import analysis as facade
from transcriptx.core.utils.config import analysis_acts
from transcriptx.core.utils.config import analysis_highlights
from transcriptx.core.utils.config import analysis_hydrate
from transcriptx.core.utils.config import analysis_summary
from transcriptx.core.utils.config import analysis_ui_presets
from transcriptx.core.utils.config import analysis_voice


@pytest.mark.unit
def test_analysis_facade_reexports_slice_classes() -> None:
    assert facade.HighlightsConfig is analysis_highlights.HighlightsConfig
    assert facade.SummaryConfig is analysis_summary.SummaryConfig
    assert facade.ActsConfig is analysis_acts.ActsConfig
    assert facade.VoiceConfig is analysis_voice.VoiceConfig
    assert facade.default_ui_presets_dict is analysis_ui_presets.default_ui_presets_dict
    assert (
        facade._hydrate_dataclass_from_pydantic
        is analysis_hydrate._hydrate_dataclass_from_pydantic
    )


@pytest.mark.unit
def test_analysis_config_still_hydrates_nested_slices() -> None:
    cfg = facade.AnalysisConfig()
    assert isinstance(cfg.highlights, analysis_highlights.HighlightsConfig)
    assert isinstance(cfg.summary, analysis_summary.SummaryConfig)
    assert isinstance(cfg.acts, analysis_acts.ActsConfig)
    assert isinstance(cfg.voice, analysis_voice.VoiceConfig)
    assert cfg.sentiment_window_size is not None
    assert "quick" in cfg.ui_presets.__dict__
