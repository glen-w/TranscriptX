"""Offline unit tests for core.analysis.ner (filename avoids auto-marker)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis import ner as named_entity_mod


@pytest.fixture
def ner_cfg() -> MagicMock:
    cfg = MagicMock()
    cfg.analysis.ner_use_light_model = False
    cfg.analysis.ner_max_segments = 5000
    cfg.analysis.ner_batch_size = 100
    cfg.analysis.ner_include_geocoding = True
    return cfg


def _fake_nlp_returning(ents: list[tuple[str, str]]):
    def _call(text: str):
        doc = MagicMock()
        ent_objs = []
        for text_v, label in ents:
            e = MagicMock()
            e.text = text_v
            e.label_ = label
            ent_objs.append(e)
        doc.ents = ent_objs
        return doc

    return _call


def _make_ner(nlp=None, cfg=None) -> named_entity_mod.NERAnalysis:
    if cfg is None:
        cfg = MagicMock()
        cfg.analysis.ner_use_light_model = False
        cfg.analysis.ner_max_segments = 5000
        cfg.analysis.ner_batch_size = 2
        cfg.analysis.ner_include_geocoding = True
    with (
        patch("transcriptx.core.analysis.ner.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.ner._get_ner_nlp",
            return_value=nlp or MagicMock(),
        ),
    ):
        return named_entity_mod.NERAnalysis()


@pytest.mark.unit
def test_get_ner_nlp_default_and_light(ner_cfg, monkeypatch) -> None:
    calls: list[str] = []

    def fake_get(name: str | None = None):
        calls.append(name or "default")
        return MagicMock(name=name or "default")

    monkeypatch.setattr(
        "transcriptx.core.utils.nlp_runtime.get_nlp_model", fake_get
    )
    with patch("transcriptx.core.analysis.ner.get_config", return_value=ner_cfg):
        named_entity_mod._get_ner_nlp()
    assert calls[-1] == "default"

    ner_cfg.analysis.ner_use_light_model = True
    calls.clear()
    with patch("transcriptx.core.analysis.ner.get_config", return_value=ner_cfg):
        named_entity_mod._get_ner_nlp()
    assert "en_core_web_sm" in calls


@pytest.mark.unit
def test_get_ner_nlp_light_falls_back_to_md(ner_cfg, monkeypatch) -> None:
    def fake_get(name: str | None = None):
        if name == "en_core_web_sm":
            raise RuntimeError("missing")
        return MagicMock(name=name)

    monkeypatch.setattr(
        "transcriptx.core.utils.nlp_runtime.get_nlp_model", fake_get
    )
    ner_cfg.analysis.ner_use_light_model = True
    with patch("transcriptx.core.analysis.ner.get_config", return_value=ner_cfg):
        model = named_entity_mod._get_ner_nlp()
    assert model is not None


@pytest.mark.unit
def test_extract_named_entities(monkeypatch) -> None:
    monkeypatch.setattr(
        named_entity_mod,
        "_get_ner_nlp",
        lambda: _fake_nlp_returning([("Paris", "GPE"), ("Google", "ORG")]),
    )
    ents = named_entity_mod.extract_named_entities("Paris and Google")
    assert ents == [("Paris", "GPE"), ("Google", "ORG")]


@pytest.mark.unit
def test_analyze_counts_entities_and_truncates(monkeypatch) -> None:
    cfg = MagicMock()
    cfg.analysis.ner_max_segments = 2
    cfg.analysis.ner_batch_size = 1
    cfg.analysis.ner_include_geocoding = False
    nlp = _fake_nlp_returning([("Paris", "GPE"), ("Alice Corp", "ORG")])
    module = _make_ner(nlp=nlp, cfg=cfg)
    monkeypatch.setattr(
        named_entity_mod,
        "extract_named_entities",
        lambda text: [("Paris", "GPE")] if "Paris" in text else [("Bob", "PERSON")],
    )
    segments = [
        {"speaker": "Alice", "speaker_db_id": 1, "text": "Paris is nice"},
        {"speaker": "Bob", "speaker_db_id": 2, "text": "Bob went too"},
        {"speaker": "Alice", "speaker_db_id": 1, "text": "extra dropped"},
        {"text": "no speaker"},
    ]
    result = module.analyze(segments)
    assert "Paris" in result["entities"] or "Bob" in result["entities"]
    assert result["summary_json"]
    assert result["all_label_counter"]
    assert "speaker_csv_rows" in result
    # Truncated to max_segments=2
    assert len(result["segments"]) == 2


@pytest.mark.unit
def test_generate_summary_text_skips_unnamed() -> None:
    module = _make_ner()
    text = module._generate_summary_text(
        {
            "Alice": Counter({"Paris": 3, "Google": 1}),
            "SPEAKER_00": Counter({"X": 9}),
        }
    )
    assert "Alice" in text
    assert "Paris: 3" in text
    assert "SPEAKER_00" not in text


@pytest.mark.unit
def test_save_results_charts_and_summary(tmp_path, monkeypatch) -> None:
    cfg = MagicMock()
    cfg.analysis.ner_include_geocoding = False
    module = _make_ner(cfg=cfg)
    results = {
        "entity_counts_per_speaker": {
            "Alice": Counter({"Paris": 2}),
            "Bob": Counter({"London": 1}),
        },
        "label_counts_per_speaker": {
            "Alice": Counter({"GPE": 2}),
            "Bob": Counter({"GPE": 1}),
        },
        "location_entities_per_speaker": {},
        "entity_sentences_per_speaker": {
            "Alice": {"Paris": ["Alice in Paris"]},
            "Bob": {"London": ["Bob in London"]},
        },
        "summary_json": {"Alice": {"Paris": 2}},
        "speaker_csv_rows": {"Alice": [["Paris", 2, "Alice in Paris"]]},
        "all_rows": [["Paris", 2, "Alice in Paris"]],
        "all_label_counter": {"GPE": 3},
    }
    output = MagicMock()
    output.save_data = MagicMock()
    output.save_chart = MagicMock()
    output.save_summary = MagicMock()
    monkeypatch.setattr(module, "_save_location_maps", MagicMock())
    module._save_results(results, output)
    assert output.save_chart.called
    assert output.save_summary.called
    assert any(
        c.args[1] == "ner-summary" for c in output.save_data.call_args_list
    )


@pytest.mark.unit
def test_save_results_triggers_geocoding(monkeypatch) -> None:
    cfg = MagicMock()
    cfg.analysis.ner_include_geocoding = True
    module = _make_ner(cfg=cfg)
    called = MagicMock()
    monkeypatch.setattr(module, "_save_location_maps", called)
    results = {
        "entity_counts_per_speaker": {"Alice": Counter({"Paris": 1})},
        "label_counts_per_speaker": {"Alice": Counter({"GPE": 1})},
        "location_entities_per_speaker": {"Alice": Counter({"Paris": 1})},
        "entity_sentences_per_speaker": {"Alice": {"Paris": ["hi"]}},
        "summary_json": {},
        "speaker_csv_rows": {},
        "all_rows": [],
        "all_label_counter": {"GPE": 1},
    }
    output = MagicMock()
    module._save_results(results, output)
    called.assert_called_once()


@pytest.mark.unit
def test_save_location_maps_records_artifacts(tmp_path, monkeypatch) -> None:
    module = named_entity_mod.NERAnalysis.__new__(named_entity_mod.NERAnalysis)
    module.module_name = "ner"

    class FakeMap:
        def __init__(self, zoom_start: int = 3) -> None:
            self.markers = []

        def save(self, path: str) -> None:
            Path(path).write_text("<html/>", encoding="utf-8")

    class FakeFolium:
        Map = FakeMap

        class Popup:
            def __init__(self, html, max_width=300):
                self.html = html

        class Marker:
            def __init__(self, latlon, popup=None):
                self.latlon = latlon
                self.popup = popup

            def add_to(self, fmap):
                fmap.markers.append(self)
                return fmap

    monkeypatch.setattr(
        "transcriptx.core.utils.lazy_imports.get_folium", lambda: FakeFolium
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.lazy_imports.get_playwright_sync_api",
        lambda silent=False: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.ner.geocode_with_cache",
        lambda items: [
            {"name": name, "lat": 1.0, "lon": 2.0} for name, _ in items
        ],
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.ner.wrap_tooltip_text",
        lambda name, speaker=None, sentence=None: f"{name}|{speaker}",
    )
    monkeypatch.setattr(
        module,
        "_render_html_to_png",
        lambda html, png, sync: png.write_bytes(b"png"),
    )

    output = MagicMock()
    output.base_name = "sample"
    output.get_output_structure.return_value = SimpleNamespace(
        module_dir=tmp_path / "out"
    )
    output._record_artifact = MagicMock()
    output._record_artifact_metadata = MagicMock()
    output.save_data = MagicMock()

    module._save_location_maps(
        {"Alice": Counter({"Paris": 1}), "Bob": Counter({"London": 1})},
        {"Alice": {"Paris": ["A"]}, "Bob": {"London": ["B"]}},
        output,
    )
    assert (tmp_path / "out" / "maps" / "html" / "sample-locations-Alice.html").exists()
    assert (tmp_path / "out" / "maps" / "html" / "sample-locations-ALL.html").exists()
    assert output._record_artifact.called
    output.save_data.assert_called()


@pytest.mark.unit
def test_render_html_to_png_playwright_none_warns(tmp_path) -> None:
    module = named_entity_mod.NERAnalysis.__new__(named_entity_mod.NERAnalysis)
    html = tmp_path / "m.html"
    html.write_text("<html/>")
    png = tmp_path / "m.png"
    with pytest.warns(UserWarning, match="Playwright not available"):
        module._render_html_to_png(html, png, sync_playwright=None)
    assert not png.exists()


@pytest.mark.unit
def test_render_html_to_png_success_and_crash_and_missing(tmp_path, monkeypatch) -> None:
    module = named_entity_mod.NERAnalysis.__new__(named_entity_mod.NERAnalysis)
    html = tmp_path / "m.html"
    html.write_text("<html/>")
    png = tmp_path / "m.png"

    class Browser:
        def __init__(self, should_fail: Exception | None = None):
            self.should_fail = should_fail

        def new_page(self, viewport=None):
            page = MagicMock()
            if self.should_fail:
                page.goto.side_effect = self.should_fail
            else:
                page.screenshot.side_effect = lambda **k: png.write_bytes(b"ok")
            return page

        def close(self):
            return None

    class Chromium:
        def __init__(self, outcomes: list):
            self.outcomes = list(outcomes)

        def launch(self, **kwargs):
            outcome = self.outcomes.pop(0) if self.outcomes else None
            if isinstance(outcome, Exception):
                raise outcome
            return Browser(should_fail=None if outcome is None else outcome)

    class P:
        def __init__(self, outcomes):
            self.chromium = Chromium(outcomes)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    # Success on chrome channel
    module._render_html_to_png(html, png, sync_playwright=lambda: P([None]))
    assert png.exists()

    # Crash path
    png2 = tmp_path / "m2.png"
    crash = RuntimeError("received signal 11")
    module._render_html_to_png(
        html, png2, sync_playwright=lambda: P([crash, crash, crash])
    )
    assert not png2.exists()

    # Missing executable → install retry fails
    png3 = tmp_path / "m3.png"
    missing = RuntimeError("Executable doesn't exist")
    monkeypatch.setattr(
        "transcriptx.core.utils.lazy_imports._ensure_playwright_browser_installed",
        lambda silent=False: False,
    )
    with pytest.warns(UserWarning, match="Chromium browser not found"):
        module._render_html_to_png(
            html, png3, sync_playwright=lambda: P([missing, missing, missing])
        )


@pytest.mark.unit
def test_create_entity_types_chart_returns_none() -> None:
    module = _make_ner()
    assert module._create_entity_types_chart("Alice", Counter({"ORG": 1})) is None
