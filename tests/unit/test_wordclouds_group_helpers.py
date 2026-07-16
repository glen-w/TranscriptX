"""Offline unit tests for wordclouds group_run pooled helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from transcriptx.core.analysis.wordclouds import group_run as gr


@pytest.mark.unit
def test_emit_pooled_global_tfidf_no_documents() -> None:
    skipped: list = []
    r = SimpleNamespace(order_index=0, transcript_path=None)
    with patch(
        "transcriptx.core.analysis.wordclouds.analysis.get_config",
        return_value=SimpleNamespace(
            analysis=SimpleNamespace(
                vectorization=SimpleNamespace(
                    wordcloud_ngram_range=(1, 1), wordcloud_max_features=10
                )
            )
        ),
    ):
        gr._emit_pooled_global_tfidf_wordcloud(
            per_transcript_results=[r],
            output_structure=MagicMock(),
            base_name="g",
            skipped_variants=skipped,
        )
    assert skipped and skipped[0]["reason_code"] == "NO_DOCUMENTS"


@pytest.mark.unit
def test_emit_pooled_global_tfidf_success(tmp_path) -> None:
    from transcriptx.core.output.group_wordcloud_output_service import (
        GroupWordcloudOutputService,
    )

    skipped: list = []
    r = SimpleNamespace(order_index=0, transcript_path=str(tmp_path / "a.json"))
    out = SimpleNamespace(
        global_data_dir=tmp_path / "g",
        speaker_data_dir=tmp_path / "s",
    )
    svc = MagicMock(spec=GroupWordcloudOutputService)
    fake_fig, fake_ax = MagicMock(), MagicMock()
    fake_wc = MagicMock()
    fake_wc.return_value.generate_from_frequencies.return_value = MagicMock()

    class FakeSparseMean:
        def mean(self, axis=0):
            return np.array([[0.5, 0.25]])

    vec = MagicMock()
    vec.fit_transform.return_value = FakeSparseMean()
    vec.get_feature_names_out.return_value = ["alpha", "beta"]

    with (
        patch(
            "transcriptx.core.analysis.wordclouds.analysis.get_config",
            return_value=SimpleNamespace(
                analysis=SimpleNamespace(
                    vectorization=SimpleNamespace(
                        wordcloud_ngram_range=(1, 1), wordcloud_max_features=10
                    )
                )
            ),
        ),
        patch("transcriptx.io.transcript_service.TranscriptService") as ts_cls,
        patch.object(gr, "tokenize_and_filter", return_value=["alpha", "beta"]),
        patch("sklearn.feature_extraction.text.TfidfVectorizer", return_value=vec),
        patch.object(gr, "_ACTIVE_OUTPUT_SERVICE", svc),
        patch.object(gr, "_get_wordcloud_class", return_value=fake_wc),
        patch.object(gr, "_wordcloud_figure", return_value=(fake_fig, fake_ax)),
        patch.object(gr, "save_global_chart", return_value="/tmp/c.png"),
        patch.object(gr, "_build_terms_payload", return_value={}),
        patch.object(gr, "_save_terms_json", return_value="/tmp/t.json"),
        patch.object(gr, "_save_wordcloud_view"),
        patch.object(gr, "_relative_to_transcript", return_value="rel"),
        patch.object(gr, "plt", MagicMock()),
    ):
        ts_cls.return_value.load_segments.return_value = [
            {"text": "alpha beta gamma renewable energy storage"}
        ]
        gr._emit_pooled_global_tfidf_wordcloud(
            per_transcript_results=[r],
            output_structure=out,
            base_name="g",
            skipped_variants=skipped,
        )
    assert skipped == []
    svc.prepare_pooled_artifact.assert_called()


@pytest.mark.unit
def test_emit_pooled_global_tfidf_empty_vocab_and_no_scores(tmp_path) -> None:
    skipped: list = []
    r = SimpleNamespace(order_index=0, transcript_path=str(tmp_path / "a.json"))
    with (
        patch(
            "transcriptx.core.analysis.wordclouds.analysis.get_config",
            return_value=SimpleNamespace(
                analysis=SimpleNamespace(
                    vectorization=SimpleNamespace(
                        wordcloud_ngram_range=(1, 1), wordcloud_max_features=10
                    )
                )
            ),
        ),
        patch("transcriptx.io.transcript_service.TranscriptService") as ts_cls,
        patch.object(gr, "tokenize_and_filter", return_value=["alpha"]),
        patch("sklearn.feature_extraction.text.TfidfVectorizer") as vec_cls,
    ):
        ts_cls.return_value.load_segments.return_value = [{"text": "alpha"}]
        vec = MagicMock()
        vec.fit_transform.side_effect = ValueError("empty vocabulary")
        vec_cls.return_value = vec
        gr._emit_pooled_global_tfidf_wordcloud(
            per_transcript_results=[r],
            output_structure=MagicMock(),
            base_name="g",
            skipped_variants=skipped,
        )
    assert skipped[-1]["reason_code"] == "EMPTY_VOCABULARY"

    skipped.clear()
    with (
        patch(
            "transcriptx.core.analysis.wordclouds.analysis.get_config",
            return_value=SimpleNamespace(
                analysis=SimpleNamespace(
                    vectorization=SimpleNamespace(
                        wordcloud_ngram_range=(1, 1), wordcloud_max_features=10
                    )
                )
            ),
        ),
        patch("transcriptx.io.transcript_service.TranscriptService") as ts_cls,
        patch.object(gr, "tokenize_and_filter", return_value=["alpha"]),
        patch("sklearn.feature_extraction.text.TfidfVectorizer") as vec_cls,
    ):
        ts_cls.return_value.load_segments.return_value = [{"text": "alpha"}]

        class ZeroMean:
            def mean(self, axis=0):
                return np.array([[0.0, 0.0]])

        vec = MagicMock()
        vec.fit_transform.return_value = ZeroMean()
        vec.get_feature_names_out.return_value = ["alpha", "beta"]
        vec_cls.return_value = vec
        gr._emit_pooled_global_tfidf_wordcloud(
            per_transcript_results=[r],
            output_structure=MagicMock(),
            base_name="g",
            skipped_variants=skipped,
        )
    assert skipped[-1]["reason_code"] == "NO_SCORES"


@pytest.mark.unit
def test_run_group_wordclouds_empty_and_basic(tmp_path) -> None:
    empty_out = gr.run_group_wordclouds({}, tmp_path, "g", "run1")
    assert empty_out["skipped_variants"] == []
    # whitespace-only chunks → early return
    out2 = gr.run_group_wordclouds({"Alice": ["  ", ""]}, tmp_path, "g", "run1")
    assert "pooled_cross_session_summary_path" not in out2

    ga = SimpleNamespace(
        wordcloud_pooled_emit_full_transcript_global=False,
        wordcloud_pooled_global_tfidf=False,
    )
    cfg = SimpleNamespace(group_analysis=ga)
    fake_svc = MagicMock()
    results = [SimpleNamespace(order_index=0, transcript_path=str(tmp_path / "a.json"))]
    with (
        patch(
            "transcriptx.core.analysis.wordclouds.analysis.get_config",
            return_value=cfg,
        ),
        patch(
            "transcriptx.core.analysis.wordclouds.group_run.GroupWordcloudOutputService",
            return_value=fake_svc,
        ),
        patch(
            "transcriptx.core.analysis.wordclouds.group_run.create_standard_output_structure"
        ) as create_out,
        patch(
            "transcriptx.core.analysis.wordclouds.analysis.generate_wordcloud",
            return_value={"alpha": 2},
        ),
        patch.object(gr, "save_freq_json_csv"),
        patch.object(gr, "use_output_service"),
        patch.object(gr, "write_json"),
    ):
        # use_output_service as context manager
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=None)
        cm.__exit__ = MagicMock(return_value=False)
        with patch.object(gr, "use_output_service", return_value=cm):
            create_out.return_value = SimpleNamespace(
                global_data_dir=tmp_path / "gd",
                speaker_data_dir=tmp_path / "sd",
            )
            (tmp_path / "gd").mkdir(parents=True, exist_ok=True)
            out = gr.run_group_wordclouds(
                {"Alice": ["alpha beta gamma"]},
                tmp_path,
                "g",
                "run1",
                group_uuid="uuid",
                per_transcript_results=results,
                aggregation_summary={
                    "excluded_speakers": [],
                    "canonical_merge_basis": "name",
                },
            )
    assert "pooled_cross_session_summary_path" in out
