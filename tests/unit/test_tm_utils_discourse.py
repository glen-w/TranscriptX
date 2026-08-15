"""Extended unit tests for topic modeling utils (discourse, prepare, optimal k)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytest.importorskip("spacy")

pytestmark = pytest.mark.requires_nlp

from transcriptx.core.analysis.topic_modeling import utils as tm_utils


@pytest.mark.unit
def test_prepare_text_data_filters_and_returns_indices() -> None:
    segments = [
        {
            "speaker": "Alice",
            "text": "renewable energy storage batteries are useful",
            "start": 1.0,
        },
        {"speaker": "Alice", "text": "  ", "start": 2.0},
        {
            "speaker": "SPEAKER_00",
            "text": "ignored diarization labels here",
            "start": 3.0,
        },
        {
            "speaker": "Bob",
            "text": "grid scale power infrastructure projects continue",
            "start": 4.0,
        },
    ]
    texts, speakers, starts, indices = tm_utils.prepare_text_data(
        segments, return_indices=True
    )
    assert len(texts) >= 1
    assert all(isinstance(t, str) and t for t in texts)
    assert len(texts) == len(speakers) == len(starts) == len(indices)
    assert "Alice" in speakers or "Bob" in speakers


@pytest.mark.unit
def test_normalize_and_generate_topic_labels() -> None:
    assert tm_utils._normalize_term_for_label("batteries").startswith("batter")
    assert tm_utils.generate_topic_labels([], []) == "General Discussion"
    label = tm_utils.generate_topic_labels(
        ["battery", "batteries", "storage", "grid"],
        [0.9, 0.8, 0.7, 0.6],
    )
    assert isinstance(label, str)
    assert label != ""


@pytest.mark.unit
def test_topic_rejected_branches() -> None:
    assert tm_utils.topic_rejected([], banned_terms={"um"}) is True
    assert tm_utils.topic_rejected(["um", "grid"], banned_terms={"um"}) is True
    assert (
        tm_utils.topic_rejected(
            ["grid", "power", "um"], banned_terms={"um"}, threshold=0.5
        )
        is False
    )


@pytest.mark.unit
def test_analyze_discourse_topics_auto_phases() -> None:
    docs = [
        {"dominant_topic": 0, "confidence": 0.9},
        {"dominant_topic": 1, "confidence": 0.5},
        {"dominant_topic": 0, "confidence": 0.7},
        {"dominant_topic": 2, "confidence": 0.4},
        {"dominant_topic": 1, "confidence": 0.6},
        {"dominant_topic": 0, "confidence": 0.8},
    ]
    out = tm_utils.analyze_discourse_topics(docs)
    assert "discourse_assignments" in out
    assert set(out["discourse_assignments"].values()) <= {
        "opening",
        "main_discussion",
        "closing",
    }
    assert (
        "topic_by_phase" in out
        or "phase_topic_distribution" in out
        or "phases" in out
        or len(out) >= 2
    )


@pytest.mark.unit
def test_analyze_discourse_topics_with_explicit_assignments() -> None:
    docs = [
        {"dominant_topic": 0, "confidence": 0.9},
        {"dominant_topic": 1, "confidence": 0.5},
    ]
    out = tm_utils.analyze_discourse_topics(
        docs, discourse_assignments={0: "opening", 1: "closing"}
    )
    assert out["discourse_assignments"][0] == "opening"
    assert out["discourse_assignments"][1] == "closing"


@pytest.mark.unit
def test_find_optimal_k_short_corpus_early_return() -> None:
    out = tm_utils.find_optimal_k(["a", "b", "c"], k_range=(2, 4), algorithm="lda")
    assert "optimal_k" in out
    assert out["optimal_k"] >= 1


@pytest.mark.unit
def test_calculate_topic_coherence_basic() -> None:
    from sklearn.feature_extraction.text import CountVectorizer

    texts = [
        "battery storage grid power",
        "battery storage renewable energy",
        "grid power infrastructure build",
    ]
    vec = CountVectorizer()
    vec.fit(texts)
    score = tm_utils.calculate_topic_coherence(["battery", "storage"], texts, vec)
    assert isinstance(score, float)


@pytest.mark.unit
def test_create_output_structure(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tm_utils, "OUTPUTS_DIR", tmp_path / "outputs")
    structure = tm_utils._create_output_structure(
        str(tmp_path / "run"), "topic_modeling"
    )
    assert "global_data_dir" in structure
    assert structure["global_data_dir"].exists()


@pytest.mark.unit
def test_to_serializable_and_safe_numpy() -> None:
    payload = {
        "i": np.int64(3),
        "f": np.float64(1.5),
        "a": np.array([1, 2]),
        "t": (np.int32(1),),
        "l": [np.float32(2.0)],
        "s": "ok",
    }
    out = tm_utils._to_serializable(payload)
    assert out["i"] == 3
    assert out["f"] == 1.5
    assert out["a"] == [1, 2]
    assert out["t"] == (1,)
    arr = tm_utils._safe_numpy_array(["1", "x", 2.5])
    assert arr.dtype == np.float64
    assert arr[1] == 0.0
    assert tm_utils._safe_numpy_array(np.array([1.0])).tolist() == [1.0]
    assert tm_utils._safe_numpy_array(3).tolist() == [3.0]


@pytest.mark.unit
def test_get_segments_and_save_json(tmp_path) -> None:
    p = tmp_path / "t.json"
    p.write_text('{"segments": [{"text": "hi"}]}', encoding="utf-8")
    assert len(tm_utils._get_segments(str(p))) == 1
    p2 = tmp_path / "list.json"
    p2.write_text('[{"text": "a"}]', encoding="utf-8")
    assert len(tm_utils._get_segments(str(p2))) == 1
    assert tm_utils._get_segments(str(tmp_path / "missing.json")) == []
    out = tmp_path / "nested" / "x.json"
    tm_utils._save_json({"a": np.int64(1)}, str(out))
    assert out.exists()
    tm_utils._notify_user("hello", technical=True, section="TEST")


@pytest.mark.unit
def test_prepare_text_data_from_windows_branches() -> None:
    assert tm_utils.prepare_text_data_from_windows(None) == ([], [], [])
    texts, speakers, times = tm_utils.prepare_text_data_from_windows(
        {
            "windows": [
                {"text": "  ", "speakers": ["Alice"], "start": 1.0},
                {
                    "text": "renewable energy storage",
                    "speakers": ["Alice", "Bob"],
                    "start": 2.0,
                },
                {"text": "grid power", "speakers": [], "start": None},
                "bad",
            ]
        }
    )
    assert len(texts) == 2
    assert "Alice" in speakers[0]
    assert speakers[1] == "window"


@pytest.mark.unit
def test_find_optimal_k_fuller_lda_path() -> None:
    # Build a corpus large enough to enter the diagnostic loop.
    words = [
        "battery",
        "storage",
        "renewable",
        "energy",
        "grid",
        "power",
        "infrastructure",
        "solar",
        "wind",
        "hydro",
        "nuclear",
        "demand",
        "supply",
        "market",
        "policy",
        "investment",
        "capacity",
        "transmission",
        "distribution",
        "efficiency",
        "carbon",
        "emission",
        "climate",
        "transition",
        "utility",
        "customer",
        "tariff",
        "pricing",
        "reliability",
        "resilience",
        "forecast",
        "planning",
        "project",
        "developer",
        "regulator",
        "innovation",
        "technology",
        "digital",
        "meter",
        "sensor",
        "data",
        "analytics",
        "model",
        "optimize",
        "schedule",
        "load",
        "peak",
        "valley",
        "flex",
        "storage2",
    ]
    texts = []
    for i in range(25):
        chunk = " ".join(words[i % 40 : (i % 40) + 12])
        texts.append(chunk + f" document number {i}")

    topic_cfg = MagicMock()
    topic_cfg.k_range = (3, 6)
    topic_cfg.max_iter_lda = 5
    topic_cfg.max_iter_nmf = 5
    topic_cfg.max_features = 200
    topic_cfg.min_df = 1
    topic_cfg.max_df = 1.0
    topic_cfg.ngram_range = (1, 1)
    topic_cfg.test_size = 0.2
    topic_cfg.random_state = 0
    topic_cfg.learning_method = "batch"
    topic_cfg.alpha_H = 0.0
    topic_cfg.tol = 1e-3
    cfg = MagicMock()
    cfg.analysis.topic_modeling = topic_cfg

    with patch.object(tm_utils, "get_config", create=True):
        pass
    with (
        patch("transcriptx.core.utils.config.get_config", return_value=cfg),
        patch.object(tm_utils, "calculate_topic_coherence", return_value=0.5),
    ):
        out = tm_utils.find_optimal_k(
            texts, k_range=(3, 5), algorithm="lda", max_iter=5
        )
    assert "optimal_k" in out
    assert out["optimal_k"] >= 3
    # Prefer diagnostics present when loop ran
    assert isinstance(out.get("diagnostics", {}), dict)


@pytest.mark.unit
def test_find_optimal_k_nmf_and_no_features() -> None:
    texts = [f"unique word{i} token{i} extra{i} content{i}" for i in range(15)]
    topic_cfg = MagicMock()
    topic_cfg.k_range = (3, 5)
    topic_cfg.max_iter_nmf = 5
    topic_cfg.max_features = 50
    topic_cfg.min_df = 1
    topic_cfg.max_df = 1.0
    topic_cfg.ngram_range = (1, 1)
    topic_cfg.test_size = 0.25
    topic_cfg.random_state = 0
    topic_cfg.alpha_H = 0.0
    topic_cfg.tol = 1e-3
    cfg = MagicMock()
    cfg.analysis.topic_modeling = topic_cfg
    with (
        patch("transcriptx.core.utils.config.get_config", return_value=cfg),
        patch.object(tm_utils, "calculate_topic_coherence", return_value=0.1),
    ):
        out = tm_utils.find_optimal_k(texts, algorithm="nmf", max_iter=5)
    assert "optimal_k" in out

    # Force zero features path
    with (
        patch("transcriptx.core.utils.config.get_config", return_value=cfg),
        patch(
            "sklearn.feature_extraction.text.CountVectorizer.fit_transform",
            return_value=MagicMock(shape=(15, 0)),
        ),
    ):
        out2 = tm_utils.find_optimal_k(
            ["a b c"] * 12, k_range=(3, 5), algorithm="lda", max_iter=2
        )
    assert out2["optimal_k"] == 3
