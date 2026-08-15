"""Unit tests for wordcloud frequency helpers."""

from __future__ import annotations

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("spacy")

pytestmark = pytest.mark.requires_nlp

from transcriptx.core.analysis.wordclouds import frequencies as freq_mod


@pytest.mark.unit
def test_save_freq_json_csv_writes_all_and_speaker(tmp_path) -> None:
    out = SimpleNamespace(
        global_data_dir=tmp_path / "g",
        speaker_data_dir=tmp_path / "s",
    )
    out.global_data_dir.mkdir()
    out.speaker_data_dir.mkdir()

    with patch.object(freq_mod, "_include_speaker_wordcloud", return_value=True):
        freq_mod.save_freq_json_csv({"hello": 3, "world": 1}, out, "base", "ALL")
        freq_mod.save_freq_json_csv({"hello": 2}, out, "base", "Alice")

    assert (out.global_data_dir / "base-ALL.json").exists()
    assert (out.global_data_dir / "base-ALL.csv").exists()
    assert (out.speaker_data_dir / "base-Alice.json").exists()
    assert (out.speaker_data_dir / "base-Alice.csv").exists()


@pytest.mark.unit
def test_save_freq_json_csv_skips_excluded_speaker(tmp_path) -> None:
    out = SimpleNamespace(
        global_data_dir=tmp_path / "g",
        speaker_data_dir=tmp_path / "s",
    )
    out.global_data_dir.mkdir()
    out.speaker_data_dir.mkdir()
    with patch.object(freq_mod, "_include_speaker_wordcloud", return_value=False):
        freq_mod.save_freq_json_csv({"hello": 1}, out, "base", "SPEAKER_00")
    assert list(out.speaker_data_dir.iterdir()) == []


@pytest.mark.unit
def test_generate_bigram_wordclouds_skips_unnamed_speakers(tmp_path) -> None:
    out = SimpleNamespace(
        global_data_dir=tmp_path / "g",
        speaker_data_dir=tmp_path / "s",
    )
    with (
        patch.object(
            freq_mod,
            "_include_speaker_wordcloud",
            side_effect=lambda s, *a, **k: s == "Glen",
        ),
        patch.object(freq_mod, "tokenize_and_filter") as tokenize,
        patch.object(freq_mod, "notify_user"),
    ):
        freq_mod.generate_bigram_wordclouds(
            {
                "SPEAKER_12": ["alpha beta gamma"],
                "Speaker 6": ["delta epsilon zeta"],
                "Glen": ["one"],
            },
            out,
            "base",
        )
    tokenize.assert_called_once_with("one")


@pytest.mark.unit
def test_generate_bigram_wordclouds_empty_skips(tmp_path) -> None:
    out = SimpleNamespace(
        global_data_dir=tmp_path / "g",
        speaker_data_dir=tmp_path / "s",
    )
    with (
        patch.object(freq_mod, "_include_speaker_wordcloud", return_value=True),
        patch.object(freq_mod, "tokenize_and_filter", return_value=["one"]),
        patch.object(freq_mod, "notify_user") as notify,
    ):
        # single token → no bigrams
        freq_mod.generate_bigram_wordclouds({"Alice": ["um"]}, out, "base")
    notify.assert_called()


@pytest.mark.unit
def test_generate_bigram_wordclouds_writes_with_stubs(tmp_path) -> None:
    out = SimpleNamespace(
        global_data_dir=tmp_path / "g",
        speaker_data_dir=tmp_path / "s",
    )
    fake_fig = MagicMock()
    fake_ax = MagicMock()
    fake_wc_cls = MagicMock()
    fake_wc_cls.return_value.generate_from_frequencies.return_value = MagicMock()

    with (
        patch.object(freq_mod, "_include_speaker_wordcloud", return_value=True),
        patch.object(
            freq_mod, "tokenize_and_filter", return_value=["alpha", "beta", "gamma"]
        ),
        patch.object(freq_mod, "_get_wordcloud_class", return_value=fake_wc_cls),
        patch.object(freq_mod, "_wordcloud_figure", return_value=(fake_fig, fake_ax)),
        patch.object(
            freq_mod, "save_speaker_chart", return_value="/tmp/c.png"
        ) as save_chart,
        patch.object(freq_mod, "_build_terms_payload", return_value={"terms": []}),
        patch.object(freq_mod, "_save_terms_json", return_value="/tmp/t.json"),
        patch.object(freq_mod, "_relative_to_transcript", return_value="rel"),
        patch.object(freq_mod, "save_freq_json_csv") as save_freq,
        patch.object(freq_mod, "plt", MagicMock()),
        patch.object(freq_mod, "notify_user"),
    ):
        freq_mod.generate_bigram_wordclouds(
            {"Alice": ["alpha beta gamma"]}, out, "base"
        )
    save_chart.assert_called()
    save_freq.assert_called()


def _enter_wc_stubs(stack: ExitStack, fake_wc_cls, fake_fig, fake_ax) -> None:
    stack.enter_context(
        patch.object(freq_mod, "_get_wordcloud_class", return_value=fake_wc_cls)
    )
    stack.enter_context(
        patch.object(freq_mod, "_wordcloud_figure", return_value=(fake_fig, fake_ax))
    )
    stack.enter_context(
        patch.object(freq_mod, "save_speaker_chart", return_value="/tmp/c.png")
    )
    stack.enter_context(
        patch.object(freq_mod, "save_global_chart", return_value="/tmp/g.png")
    )
    stack.enter_context(
        patch.object(freq_mod, "_build_terms_payload", return_value={"terms": []})
    )
    stack.enter_context(
        patch.object(freq_mod, "_save_terms_json", return_value="/tmp/t.json")
    )
    stack.enter_context(patch.object(freq_mod, "_save_wordcloud_view"))
    stack.enter_context(
        patch.object(freq_mod, "_relative_to_transcript", return_value="rel")
    )
    stack.enter_context(patch.object(freq_mod, "save_freq_json_csv"))
    stack.enter_context(patch.object(freq_mod, "plt", MagicMock()))
    stack.enter_context(patch.object(freq_mod, "notify_user"))


@pytest.mark.unit
def test_generate_tfidf_wordclouds_empty_docs(tmp_path) -> None:
    out = SimpleNamespace(
        global_data_dir=tmp_path / "g",
        speaker_data_dir=tmp_path / "s",
    )
    config = SimpleNamespace(
        analysis=SimpleNamespace(
            vectorization=SimpleNamespace(
                wordcloud_ngram_range=(1, 1), wordcloud_max_features=50
            ),
        )
    )
    with (
        patch.object(freq_mod, "get_config", return_value=config),
        patch.object(freq_mod, "_include_speaker_wordcloud", return_value=True),
        patch.object(freq_mod, "tokenize_and_filter", return_value=[]),
        patch.object(freq_mod, "notify_user") as notify,
    ):
        freq_mod.generate_tfidf_wordclouds({"Alice": ["um"]}, out, "base")
    notify.assert_called()


@pytest.mark.unit
def test_generate_tfidf_wordclouds_success_and_empty_vocab(tmp_path) -> None:
    out = SimpleNamespace(
        global_data_dir=tmp_path / "g",
        speaker_data_dir=tmp_path / "s",
    )
    out.global_data_dir.mkdir(parents=True)
    out.speaker_data_dir.mkdir(parents=True)
    config = SimpleNamespace(
        analysis=SimpleNamespace(
            vectorization=SimpleNamespace(
                wordcloud_ngram_range=(1, 1), wordcloud_max_features=50
            ),
        )
    )
    fake_fig, fake_ax = MagicMock(), MagicMock()
    fake_wc_cls = MagicMock()
    fake_wc_cls.return_value.generate_from_frequencies.return_value = MagicMock()

    # Empty vocabulary branch
    with (
        patch.object(freq_mod, "get_config", return_value=config),
        patch.object(freq_mod, "tokenize_and_filter", return_value=["alpha", "beta"]),
        patch.object(freq_mod, "_include_speaker_wordcloud", return_value=True),
        patch("sklearn.feature_extraction.text.TfidfVectorizer") as vec_cls,
        patch.object(freq_mod, "notify_user") as notify,
    ):
        vec = MagicMock()
        vec.fit_transform.side_effect = ValueError("empty vocabulary")
        vec_cls.return_value = vec
        freq_mod.generate_tfidf_wordclouds({"Alice": ["alpha beta"]}, out, "base")
    notify.assert_called()

    # Success path: return dense rows (non-spmatrix branch)
    import numpy as np

    matrix = MagicMock()
    matrix.__getitem__ = lambda self, idx: np.array([[0.5, 0.0, 0.2]])
    global_matrix = MagicMock()
    global_matrix.__getitem__ = lambda self, idx: np.array([[0.5, 0.0, 0.2]])

    vec2 = MagicMock()
    vec2.fit_transform.side_effect = [matrix, global_matrix]
    vec2.get_feature_names_out.return_value = ["alpha", "beta", "gamma"]

    with ExitStack() as stack:
        stack.enter_context(patch.object(freq_mod, "get_config", return_value=config))
        stack.enter_context(
            patch.object(
                freq_mod, "tokenize_and_filter", return_value=["alpha", "beta", "gamma"]
            )
        )
        stack.enter_context(
            patch.object(
                freq_mod,
                "_include_speaker_wordcloud",
                side_effect=lambda s, *a, **k: s == "Alice",
            )
        )
        stack.enter_context(
            patch("sklearn.feature_extraction.text.TfidfVectorizer", return_value=vec2)
        )
        _enter_wc_stubs(stack, fake_wc_cls, fake_fig, fake_ax)
        freq_mod.generate_tfidf_wordclouds(
            {"Alice": ["alpha beta gamma"], "SPEAKER_00": ["x"]}, out, "base"
        )


@pytest.mark.unit
def test_generate_bigram_tfidf_wordclouds_paths(tmp_path) -> None:
    out = SimpleNamespace(
        global_data_dir=tmp_path / "g",
        speaker_data_dir=tmp_path / "s",
    )
    config = SimpleNamespace(
        analysis=SimpleNamespace(
            vectorization=SimpleNamespace(
                wordcloud_ngram_range=(2, 2), wordcloud_max_features=50
            )
        )
    )
    with (
        patch.object(freq_mod, "get_config", return_value=config),
        patch.object(freq_mod, "_include_speaker_wordcloud", return_value=True),
        patch.object(freq_mod, "tokenize_and_filter", return_value=[]),
        patch.object(freq_mod, "notify_user") as notify,
    ):
        freq_mod.generate_bigram_tfidf_wordclouds({"Alice": ["x"]}, out, "base")
    notify.assert_called()

    fake_fig, fake_ax = MagicMock(), MagicMock()
    fake_wc_cls = MagicMock()
    fake_wc_cls.return_value.generate_from_frequencies.return_value = MagicMock()

    import numpy as np

    matrix = MagicMock()
    matrix.__getitem__ = lambda self, idx: np.array([[0.4, 0.3]])
    global_matrix = MagicMock()
    global_matrix.__getitem__ = lambda self, idx: np.array([[0.4, 0.3]])
    vec = MagicMock()
    vec.fit_transform.side_effect = [matrix, global_matrix]
    vec.get_feature_names_out.return_value = ["alpha beta", "beta gamma"]

    with ExitStack() as stack:
        stack.enter_context(patch.object(freq_mod, "get_config", return_value=config))
        stack.enter_context(
            patch.object(freq_mod, "_include_speaker_wordcloud", return_value=True)
        )
        stack.enter_context(
            patch.object(
                freq_mod, "tokenize_and_filter", return_value=["alpha", "beta", "gamma"]
            )
        )
        stack.enter_context(
            patch("sklearn.feature_extraction.text.TfidfVectorizer", return_value=vec)
        )
        _enter_wc_stubs(stack, fake_wc_cls, fake_fig, fake_ax)
        freq_mod.generate_bigram_tfidf_wordclouds(
            {"Alice": ["alpha beta gamma"]}, out, "base"
        )

    # empty vocabulary
    with (
        patch.object(freq_mod, "get_config", return_value=config),
        patch.object(freq_mod, "_include_speaker_wordcloud", return_value=True),
        patch.object(freq_mod, "tokenize_and_filter", return_value=["alpha", "beta"]),
        patch("sklearn.feature_extraction.text.TfidfVectorizer") as vec_cls,
        patch.object(freq_mod, "notify_user") as notify2,
    ):
        v = MagicMock()
        v.fit_transform.side_effect = ValueError("empty vocabulary")
        vec_cls.return_value = v
        freq_mod.generate_bigram_tfidf_wordclouds({"Alice": ["a b"]}, out, "base")
    notify2.assert_called()


@pytest.mark.unit
def test_generate_tic_and_pos_wordclouds(tmp_path) -> None:
    out = SimpleNamespace(
        global_data_dir=tmp_path / "g",
        speaker_data_dir=tmp_path / "s",
    )
    fake_fig, fake_ax = MagicMock(), MagicMock()
    fake_wc_cls = MagicMock()
    fake_wc_cls.return_value.generate_from_frequencies.return_value = MagicMock()
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                freq_mod,
                "_include_speaker_wordcloud",
                side_effect=lambda s, *a, **k: s == "Alice",
            )
        )
        stack.enter_context(
            patch.object(
                freq_mod, "extract_tics_from_text", return_value=["um", "um", "like"]
            )
        )
        _enter_wc_stubs(stack, fake_wc_cls, fake_fig, fake_ax)
        freq_mod.generate_tic_wordclouds(
            {"Alice": ["um like yeah"], "SPEAKER_00": ["um"]}, out, "base"
        )

    # empty tics skip
    with (
        patch.object(freq_mod, "_include_speaker_wordcloud", return_value=True),
        patch.object(freq_mod, "extract_tics_from_text", return_value=[]),
        patch.object(freq_mod, "_get_wordcloud_class") as wc,
    ):
        freq_mod.generate_tic_wordclouds({"Alice": ["hello"]}, out, "base")
    wc.assert_not_called()

    # POS wordclouds
    tok = MagicMock()
    tok.text = "battery"
    tok.pos_ = "NOUN"
    doc = MagicMock()
    doc.__iter__ = lambda self: iter([tok])
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(freq_mod, "_include_speaker_wordcloud", return_value=True)
        )
        stack.enter_context(patch.object(freq_mod, "nlp", return_value=doc))
        stack.enter_context(patch.object(freq_mod, "ALL_STOPWORDS", set()))
        _enter_wc_stubs(stack, fake_wc_cls, fake_fig, fake_ax)
        freq_mod.generate_pos_wordclouds(
            {"Alice": ["Battery storage works"]}, out, "base", "noun"
        )

    # unknown pos filter → empty tags → skip
    with (
        patch.object(freq_mod, "_include_speaker_wordcloud", return_value=True),
        patch.object(freq_mod, "nlp", return_value=doc),
        patch.object(freq_mod, "ALL_STOPWORDS", set()),
        patch.object(freq_mod, "_get_wordcloud_class") as wc2,
    ):
        freq_mod.generate_pos_wordclouds({"Alice": ["Battery"]}, out, "base", "unknown")
    wc2.assert_not_called()
