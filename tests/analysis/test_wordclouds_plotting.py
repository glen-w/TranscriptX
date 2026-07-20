"""Unit tests for wordcloud plotting helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.wordclouds import plotting as plot_mod
from transcriptx.core.analysis.wordclouds import output_bridge as bridge_mod


@pytest.mark.unit
def test_include_speaker_wordcloud_rejects_unnamed_labels() -> None:
    config = MagicMock()
    config.analysis.exclude_unidentified_from_speaker_charts = True
    with (
        patch.object(bridge_mod, "_ACTIVE_OUTPUT_SERVICE", None),
        patch.object(bridge_mod, "get_config", return_value=config),
        patch.object(bridge_mod, "_get_ignored_ids", return_value=set()),
        patch.object(bridge_mod, "_resolve_speaker_key", side_effect=lambda s, *a: s),
    ):
        assert bridge_mod._include_speaker_wordcloud("Glen") is True
        assert bridge_mod._include_speaker_wordcloud("SPEAKER_12") is False
        assert bridge_mod._include_speaker_wordcloud("Speaker 13") is False
        assert bridge_mod._include_speaker_wordcloud("Speaker 6") is False
        assert bridge_mod._include_speaker_wordcloud("wordcloud-ALL") is True


@pytest.mark.unit
def test_generate_wordcloud_skips_unnamed_without_notify() -> None:
    with (
        patch.object(plot_mod, "_include_speaker_wordcloud", return_value=False),
        patch.object(plot_mod, "tokenize_and_filter") as tokenize,
        patch.object(plot_mod, "notify_user") as notify,
    ):
        freq = plot_mod.generate_wordcloud(
            "alpha beta gamma",
            output_structure=MagicMock(),
            base_name="base",
            speaker="SPEAKER_12",
            filename="wordcloud",
        )
    assert freq == {}
    tokenize.assert_not_called()
    notify.assert_not_called()


@pytest.mark.unit
def test_generate_wordcloud_notifies_only_when_saved() -> None:
    fake_fig, fake_ax = MagicMock(), MagicMock()
    fake_wc_cls = MagicMock()
    fake_wc_cls.return_value.generate_from_frequencies.return_value = MagicMock()
    with (
        patch.object(plot_mod, "_include_speaker_wordcloud", return_value=True),
        patch.object(plot_mod, "tokenize_and_filter", return_value=["alpha", "beta"]),
        patch.object(plot_mod, "_get_wordcloud_class", return_value=fake_wc_cls),
        patch.object(plot_mod, "_wordcloud_figure", return_value=(fake_fig, fake_ax)),
        patch.object(plot_mod, "save_speaker_chart", return_value=None),
        patch.object(plot_mod, "_build_terms_payload", return_value={"terms": []}),
        patch.object(plot_mod, "_save_terms_json", return_value=None),
        patch.object(plot_mod, "_save_wordcloud_view"),
        patch.object(plot_mod, "plt", MagicMock()),
        patch.object(plot_mod, "notify_user") as notify,
    ):
        freq = plot_mod.generate_wordcloud(
            "alpha beta",
            output_structure=MagicMock(),
            base_name="base",
            speaker="Glen",
            filename="wordcloud",
        )
    assert freq
    notify.assert_not_called()
