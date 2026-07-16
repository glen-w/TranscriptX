"""Offline unit tests for core.analysis.emotion (filename avoids auto-marker)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis import emotion as affect_mod


@pytest.fixture
def affect_cfg() -> MagicMock:
    cfg = MagicMock()
    cfg.analysis.emotion_model_name = "test/model"
    cfg.analysis.emotion_output_mode = "top1"
    cfg.analysis.emotion_score_threshold = 0.30
    return cfg


def _make_module(
    *,
    nrclex=None,
    emotion_model=None,
    mode: str = "top1",
    threshold: float = 0.30,
) -> affect_mod.EmotionAnalysis:
    cfg = MagicMock()
    cfg.analysis.emotion_model_name = "test/model"
    cfg.analysis.emotion_output_mode = mode
    cfg.analysis.emotion_score_threshold = threshold
    with (
        patch("transcriptx.core.utils.config.get_config", return_value=cfg),
        patch("transcriptx.core.analysis.emotion._load_nrclex", return_value=nrclex),
        patch(
            "transcriptx.core.analysis.emotion._load_emotion_model",
            return_value=emotion_model,
        ),
    ):
        return affect_mod.EmotionAnalysis()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_extract_nrc_scores_raw_and_affect_and_empty() -> None:
    raw = SimpleNamespace(raw_emotion_scores={"joy": 2, "anger": 1, "x": "bad"})
    assert affect_mod._extract_nrc_emotion_scores(raw) == {"joy": 2.0, "anger": 1.0}

    affect = SimpleNamespace(
        affect_frequencies={"anticip": 0.4, "fear": 0.2, "meta": "x"}
    )
    scores = affect_mod._extract_nrc_emotion_scores(affect)
    assert scores["anticipation"] == 0.4
    assert scores["fear"] == 0.2
    assert "meta" not in scores

    assert affect_mod._extract_nrc_emotion_scores(SimpleNamespace()) == {}


@pytest.mark.unit
def test_nrclex_analyze_legacy_and_load_raw_text() -> None:
    class Legacy:
        def __init__(self, text: str) -> None:
            self.text = text

    leg = affect_mod._nrclex_analyze(Legacy, "hello")
    assert leg.text == "hello"

    class Modern:
        def __init__(self) -> None:
            self.text = ""

        def load_raw_text(self, text: str) -> None:
            self.text = text

    mod = affect_mod._nrclex_analyze(Modern, "world")
    assert mod.text == "world"


@pytest.mark.unit
def test_ensure_textblob_corpora_downloads_disabled(monkeypatch) -> None:
    monkeypatch.setattr(affect_mod, "downloads_disabled", lambda: True)
    with pytest.raises(RuntimeError, match="disabled"):
        affect_mod._ensure_textblob_corpora()


@pytest.mark.unit
def test_ensure_textblob_corpora_success_and_notify_fallback(monkeypatch) -> None:
    monkeypatch.setattr(affect_mod, "downloads_disabled", lambda: False)
    calls: list[str] = []

    def fake_download_all() -> None:
        calls.append("dl")

    fake_pkg = SimpleNamespace(download_all=fake_download_all)
    with patch.dict("sys.modules", {"textblob.download_corpora": fake_pkg}):
        with patch(
            "transcriptx.core.analysis.emotion.notify_user",
            side_effect=RuntimeError("no notify"),
        ):
            affect_mod._ensure_textblob_corpora()
    assert calls == ["dl"]


@pytest.mark.unit
def test_ensure_textblob_corpora_raises_after_failed_download(monkeypatch) -> None:
    monkeypatch.setattr(affect_mod, "downloads_disabled", lambda: False)
    fake_pkg = SimpleNamespace(
        download_all=lambda: (_ for _ in ()).throw(OSError("boom"))
    )
    with patch.dict("sys.modules", {"textblob.download_corpora": fake_pkg}):
        with patch(
            "transcriptx.core.analysis.emotion.notify_user",
            side_effect=RuntimeError("gone"),
        ):
            with pytest.raises(OSError, match="boom"):
                affect_mod._ensure_textblob_corpora()


@pytest.mark.unit
def test_load_nrclex_success_path(monkeypatch) -> None:
    class FakeNRC:
        def __init__(self, text: str = "") -> None:
            self.raw_emotion_scores = {"joy": 1.0}

    monkeypatch.setitem(
        __import__("sys").modules,
        "nrclex",
        SimpleNamespace(NRCLex=FakeNRC),
    )
    loaded = affect_mod._load_nrclex()
    assert loaded is FakeNRC


@pytest.mark.unit
def test_load_nrclex_retry_then_none(monkeypatch) -> None:
    monkeypatch.setitem(
        __import__("sys").modules,
        "nrclex",
        SimpleNamespace(NRCLex=None),
    )
    monkeypatch.setattr(
        affect_mod,
        "_ensure_textblob_corpora",
        lambda: (_ for _ in ()).throw(RuntimeError("no corpora")),
    )
    with patch(
        "transcriptx.core.analysis.emotion.notify_user",
        side_effect=RuntimeError("gone"),
    ):
        assert affect_mod._load_nrclex() is None


@pytest.mark.unit
def test_load_emotion_model_disabled_and_failure(monkeypatch, affect_cfg) -> None:
    monkeypatch.setattr(affect_mod, "downloads_disabled", lambda: True)
    assert affect_mod._load_emotion_model("m") is None

    monkeypatch.setattr(affect_mod, "downloads_disabled", lambda: False)
    with (
        patch("transcriptx.core.utils.config.get_config", return_value=affect_cfg),
        patch(
            "transcriptx.core.utils.lazy_imports.get_transformers",
            side_effect=RuntimeError("no transformers"),
        ),
        patch(
            "transcriptx.core.analysis.emotion.notify_user",
            side_effect=RuntimeError("gone"),
        ),
    ):
        assert affect_mod._load_emotion_model(None) is None


@pytest.mark.unit
def test_load_emotion_model_success(monkeypatch, affect_cfg) -> None:
    monkeypatch.setattr(affect_mod, "downloads_disabled", lambda: False)
    pipe = MagicMock(name="pipe")
    transformers = SimpleNamespace(pipeline=MagicMock(return_value=pipe))
    with (
        patch("transcriptx.core.utils.config.get_config", return_value=affect_cfg),
        patch(
            "transcriptx.core.utils.lazy_imports.get_transformers",
            return_value=transformers,
        ),
        patch("transcriptx.core.analysis.emotion.suppress_stdout_stderr"),
        patch("transcriptx.core.analysis.emotion.spinner"),
    ):
        assert affect_mod._load_emotion_model(None) is pipe
    transformers.pipeline.assert_called_once()


# ---------------------------------------------------------------------------
# EmotionAnalysis
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_pipeline_modes() -> None:
    obj = _make_module(mode="top1")
    primary, scores = obj._parse_pipeline_emotion_result(
        [{"label": "joy", "score": 0.7}, {"label": "sadness", "score": 0.2}]
    )
    assert primary == "joy"
    assert scores == {"joy": 0.7}

    obj.emotion_output_mode = "multilabel"
    obj.emotion_score_threshold = 0.3
    primary, scores = obj._parse_pipeline_emotion_result(
        [{"label": "joy", "score": 0.7}, {"label": "sadness", "score": 0.2}]
    )
    assert primary == "joy"
    assert scores == {"joy": 0.7}

    assert obj._parse_pipeline_emotion_result([]) == ("", {})


@pytest.mark.unit
def test_compute_nrc_emotions_normalizes() -> None:
    class FakeNRC:
        def __init__(self, text: str = "") -> None:
            self.raw_emotion_scores = {"joy": 2.0, "anger": 2.0}

    obj = _make_module(nrclex=FakeNRC)
    scores = obj._compute_nrc_emotions("happy sad")
    assert scores == {"joy": 0.5, "anger": 0.5}

    empty = _make_module(nrclex=None)
    assert empty._compute_nrc_emotions("x") == {}


@pytest.mark.unit
def test_analyze_with_hf_and_nrc_fallback() -> None:
    class FakeNRC:
        def __init__(self, text: str = "") -> None:
            self.raw_emotion_scores = {"joy": 1.0, "anger": 0.0}

    mock_model = MagicMock()
    mock_model.return_value = [[{"label": "joy", "score": 0.9}]]
    obj = _make_module(nrclex=FakeNRC, emotion_model=mock_model)
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "I am happy today",
            "start": 0.0,
            "end": 1.0,
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "",
            "start": 1.0,
            "end": 2.0,
        },
        {"text": "no speaker"},
    ]
    result = obj.analyze(segments)
    assert result["segments"] is segments
    assert segments[0]["context_emotion_source"] == "hf"
    assert segments[0]["context_emotion_primary"] == "joy"
    assert "nrc_emotion" in segments[0]
    assert "Alice" in result["speaker_stats"]
    assert "emotions" in result


@pytest.mark.unit
def test_analyze_nrc_fills_when_hf_empty_labels() -> None:
    class FakeNRC:
        def __init__(self, text: str = "") -> None:
            self.raw_emotion_scores = {"sadness": 3.0, "joy": 1.0}

    mock_model = MagicMock()
    # Empty pipeline result after threshold → primary "" but source still hf
    mock_model.return_value = [[]]
    obj = _make_module(nrclex=FakeNRC, emotion_model=mock_model)
    # Force contextual path to set empty primary with hf source
    seg = {
        "speaker": "Alice",
        "speaker_db_id": 1,
        "text": "feeling down",
        "start": 0.0,
        "end": 1.0,
        "context_emotion_source": "hf",
        "context_emotion_primary": "",
        "context_emotion_scores": {},
    }
    # Skip HF recompute by clearing model so NRC fallback runs
    obj.emotion_model = None
    result = obj.analyze([seg])
    assert seg["context_emotion_source"] == "nrc"
    assert seg["context_emotion_primary"] == "sadness"
    assert result["nrc_scores"]


@pytest.mark.unit
def test_analyze_sets_none_source_without_scores() -> None:
    obj = _make_module(nrclex=None, emotion_model=None)
    seg = {
        "speaker": "Alice",
        "speaker_db_id": 1,
        "text": "hello",
        "start": 0.0,
        "end": 1.0,
    }
    obj.analyze([seg])
    assert seg["context_emotion_source"] == "none"
    assert seg["context_emotion_primary"] == ""


@pytest.mark.unit
def test_save_results_and_radar(tmp_path, monkeypatch) -> None:
    obj = _make_module()
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "a",
            "nrc_emotion": {"joy": 0.6},
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "b",
            "nrc_emotion": {"anger": 0.4},
        },
    ]
    results = {
        "segments_with_emotion": segments,
        "nrc_scores": {"Alice": {"joy": 0.6}, "Bob": {"anger": 0.4}},
        "combined_rows": [{"speaker": "Alice", "joy": 0.6}],
        "contextual_all": {"Alice": ["joy"]},
        "contextual_examples": {},
        "all_scores": {"joy": 0.5, "anger": 0.5},
        "global_stats": {"joy": 0.5},
        "speaker_stats": {"Alice": {"joy": 0.6}},
    }

    fake_fig = MagicMock()
    plt = MagicMock()
    plt.close = MagicMock()
    monkeypatch.setattr(
        "transcriptx.core.utils.lazy_imports.get_matplotlib_pyplot",
        lambda: plt,
    )
    monkeypatch.setattr(obj, "_create_emotion_radar", lambda *a, **k: fake_fig)
    monkeypatch.setattr(
        "transcriptx.core.analysis.affect.output_helpers.get_enriched_transcript_path",
        lambda path, mod: str(tmp_path / "enriched.json"),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.affect.output_helpers.save_transcript",
        lambda *a, **k: None,
    )

    output = MagicMock()
    output.transcript_path = str(tmp_path / "t.json")
    output.save_data = MagicMock()
    output.save_chart = MagicMock()
    output.save_summary = MagicMock()

    obj._save_results(results, output)
    assert output.save_data.called
    assert output.save_chart.called
    assert output.save_summary.called
    plt.close.assert_called()


@pytest.mark.unit
def test_create_emotion_radar_returns_figure(monkeypatch) -> None:
    obj = _make_module()
    fig = MagicMock()
    ax = MagicMock()
    plt = MagicMock()
    plt.subplots.return_value = (fig, ax)
    monkeypatch.setattr(
        "transcriptx.core.utils.lazy_imports.get_matplotlib_pyplot",
        lambda: plt,
    )
    out = obj._create_emotion_radar("Alice", {"joy": 0.5, "anger": 0.25})
    assert out is fig
    ax.plot.assert_called()


@pytest.mark.unit
def test_compute_nrc_emotions_module_level(monkeypatch) -> None:
    class FakeNRC:
        def __init__(self, text: str = "") -> None:
            self.raw_emotion_scores = {"joy": 1.0}

    monkeypatch.setattr(affect_mod, "_load_nrclex", lambda: FakeNRC)
    scores = affect_mod.compute_nrc_emotions("happy")
    assert scores == {"joy": 1.0}

    monkeypatch.setattr(affect_mod, "_load_nrclex", lambda: None)
    assert affect_mod.compute_nrc_emotions("x") == {}
