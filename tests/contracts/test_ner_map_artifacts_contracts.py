"""Contract tests for ner map artifacts contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from transcriptx.core.analysis.ner import NERAnalysis


@dataclass
class _OutputStructure:
    module_dir: Path


class _OutputServiceFake:
    def __init__(self, module_dir: Path, base_name: str = "sample") -> None:
        self._structure = _OutputStructure(module_dir=module_dir)
        self.base_name = base_name
        self.artifacts: list[tuple[Path, str, str]] = []
        self.metadata: dict[str, dict[str, Any]] = {}

    def get_output_structure(self) -> _OutputStructure:
        return self._structure

    def _record_artifact(
        self, path: Path, fmt: str, artifact_role: str = "primary"
    ) -> None:
        self.artifacts.append((path, fmt, artifact_role))

    def _record_artifact_metadata(self, path: Path, metadata: dict[str, Any]) -> None:
        self.metadata[path.name] = metadata

    def save_data(self, payload: Any, name: str, format_type: str = "json") -> None:
        extension = "json" if format_type == "json" else format_type
        out_path = self._structure.module_dir / f"{name}.{extension}"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(str(payload), encoding="utf-8")


class _FakeMap:
    def __init__(self, zoom_start: int = 3) -> None:
        self.zoom_start = zoom_start
        self.markers: list[dict[str, Any]] = []

    def save(self, path: str) -> None:
        Path(path).write_text("<html>fake-map</html>", encoding="utf-8")


class _FakePopup:
    def __init__(self, html: str, max_width: int = 300) -> None:
        self.html = html
        self.max_width = max_width


class _FakeMarker:
    def __init__(
        self, latlon: list[float], tooltip: str = "", popup: _FakePopup | None = None
    ) -> None:
        self.latlon = latlon
        self.tooltip = tooltip
        self.popup = popup

    def add_to(self, fmap: _FakeMap) -> _FakeMap:
        fmap.markers.append(
            {"latlon": self.latlon, "tooltip": self.tooltip, "popup": self.popup}
        )
        return fmap


class _FakeFolium:
    Map = _FakeMap
    Popup = _FakePopup
    Marker = _FakeMarker


def _ner_instance() -> NERAnalysis:
    ner = NERAnalysis.__new__(NERAnalysis)
    ner.module_name = "ner"
    return ner


def _patch_maps_deps(monkeypatch, ner: NERAnalysis, write_png: bool) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.lazy_imports.get_folium", lambda: _FakeFolium
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.lazy_imports.get_playwright_sync_api",
        lambda silent=False: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.ner.geocode_with_cache",
        lambda items: [
            {"name": name, "lat": idx + 1.0, "lon": idx + 2.0}
            for idx, (name, _count) in enumerate(items)
        ],
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.ner.wrap_tooltip_text",
        lambda name, speaker=None, sentence=None: f"{name}|{speaker}|{sentence}",
    )
    if write_png:
        monkeypatch.setattr(
            ner,
            "_render_html_to_png",
            lambda html_path, png_path, sync_playwright: png_path.write_bytes(b"png"),
        )
    else:
        monkeypatch.setattr(
            ner,
            "_render_html_to_png",
            lambda html_path, png_path, sync_playwright: None,
        )


def test_ner_location_maps_filesystem_contract(tmp_path: Path, monkeypatch) -> None:
    ner = _ner_instance()
    output_service = _OutputServiceFake(tmp_path / "ner")
    _patch_maps_deps(monkeypatch, ner, write_png=True)

    locations = {"Alice": {"Paris": 2}, "Bob": {"London": 1}}
    sentences = {
        "Alice": {"Paris": ["Alice in Paris."]},
        "Bob": {"London": ["Bob in London."]},
    }
    ner._save_location_maps(locations, sentences, output_service)

    html_dir = tmp_path / "ner" / "maps" / "html"
    image_dir = tmp_path / "ner" / "maps" / "images"
    assert (html_dir / "sample-locations-Alice.html").exists()
    assert (html_dir / "sample-locations-Bob.html").exists()
    assert (html_dir / "sample-locations-ALL.html").exists()
    assert (image_dir / "sample-locations-Alice.png").exists()
    assert (image_dir / "sample-locations-Bob.png").exists()
    assert (image_dir / "sample-locations-ALL.png").exists()
    assert (tmp_path / "ner" / "ner-locations.json").exists()


def test_ner_location_maps_metadata_contract(tmp_path: Path, monkeypatch) -> None:
    ner = _ner_instance()
    output_service = _OutputServiceFake(tmp_path / "ner")
    _patch_maps_deps(monkeypatch, ner, write_png=True)

    ner._save_location_maps(
        {"Alice": {"Paris": 1}, "Bob": {"London": 1}},
        {"Alice": {"Paris": ["A"]}, "Bob": {"London": ["B"]}},
        output_service,
    )

    alice_html = output_service.metadata["sample-locations-Alice.html"]
    alice_png = output_service.metadata["sample-locations-Alice.png"]
    global_html = output_service.metadata["sample-locations-ALL.html"]
    global_png = output_service.metadata["sample-locations-ALL.png"]

    assert alice_html["render_hint"] == "dynamic"
    assert alice_html["renderer"] == "folium"
    assert alice_html["scope"] == "speaker"
    assert alice_html["speaker"] == "Alice"

    assert alice_png["render_hint"] == "static"
    assert alice_png["renderer"] == "playwright"
    assert alice_png["scope"] == "speaker"
    assert alice_png["speaker"] == "Alice"

    assert global_html["render_hint"] == "dynamic"
    assert global_html["scope"] == "global"
    assert "speaker" not in global_html

    assert global_png["render_hint"] == "static"
    assert global_png["scope"] == "global"


def test_ner_location_maps_tooltip_popup_contract(tmp_path: Path, monkeypatch) -> None:
    ner = _ner_instance()
    output_service = _OutputServiceFake(tmp_path / "ner")
    wrap_calls: list[tuple[str, str, str]] = []

    def _wrap(
        name: str, speaker: str | None = None, sentence: str | None = None
    ) -> str:
        wrap_calls.append((name, speaker or "", sentence or ""))
        return f"{name}|{speaker}|{sentence}"

    monkeypatch.setattr(
        "transcriptx.core.utils.lazy_imports.get_folium", lambda: _FakeFolium
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.lazy_imports.get_playwright_sync_api",
        lambda silent=False: None,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.ner.geocode_with_cache",
        lambda items: [
            {"name": name, "lat": 10.0, "lon": 20.0} for name, _count in items
        ],
    )
    monkeypatch.setattr(
        ner, "_render_html_to_png", lambda html_path, png_path, sync_playwright: None
    )
    monkeypatch.setattr("transcriptx.core.analysis.ner.wrap_tooltip_text", _wrap)

    ner._save_location_maps(
        {"Alice": {"Paris": 1}, "Bob": {"London": 1}},
        {
            "Alice": {"Paris": ["Alice said Paris."]},
            "Bob": {"London": ["Bob said London."]},
        },
        output_service,
    )

    assert ("Paris", "Alice", "Alice said Paris.") in wrap_calls
    assert ("London", "Bob", "Bob said London.") in wrap_calls


def test_ner_location_maps_render_fallback_keeps_html(
    tmp_path: Path, monkeypatch
) -> None:
    ner = _ner_instance()
    output_service = _OutputServiceFake(tmp_path / "ner")
    _patch_maps_deps(monkeypatch, ner, write_png=False)

    ner._save_location_maps(
        {"Alice": {"Paris": 1}, "Bob": {"London": 1}},
        {"Alice": {"Paris": ["A"]}, "Bob": {"London": ["B"]}},
        output_service,
    )

    html_artifacts = [
        path.name for path, fmt, _role in output_service.artifacts if fmt == "html"
    ]
    png_artifacts = [
        path.name for path, fmt, _role in output_service.artifacts if fmt == "png"
    ]

    assert "sample-locations-Alice.html" in html_artifacts
    assert "sample-locations-ALL.html" in html_artifacts
    assert not png_artifacts


def test_ner_location_maps_soft_skip_without_folium(
    tmp_path: Path, monkeypatch
) -> None:
    """Maps HTML/PNG are optional ([maps]); missing folium must not fail NER JSON."""
    import warnings

    ner = _ner_instance()
    output_service = _OutputServiceFake(tmp_path / "ner")
    monkeypatch.setattr(
        "transcriptx.core.utils.lazy_imports.get_folium",
        lambda: (_ for _ in ()).throw(
            ImportError(
                "folium is required for map visualization. "
                "Install with: pip install -e '.[maps]' "
                "(from a TranscriptX git checkout; not on PyPI)"
            )
        ),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.ner.geocode_with_cache",
        lambda items: [
            {"name": name, "lat": 1.0, "lon": 2.0} for name, _count in items
        ],
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ner._save_location_maps(
            {"Alice": {"Paris": 1}},
            {"Alice": {"Paris": ["A"]}},
            output_service,
            location_mentions_per_speaker={
                "Alice": {
                    "Paris": [
                        {"text": "A", "segment_index": 3, "start": 12.5},
                    ]
                }
            },
        )

    assert output_service.artifacts == []
    assert (tmp_path / "ner" / "ner-locations.json").exists()
    assert any("Skipping NER location map HTML/PNG" in str(w.message) for w in caught)


def test_ner_location_maps_include_segment_refs(tmp_path: Path, monkeypatch) -> None:
    """ner-locations records include segment_index and start when mentions provided."""
    import ast

    ner = _ner_instance()
    output_service = _OutputServiceFake(tmp_path / "ner")
    _patch_maps_deps(monkeypatch, ner, write_png=False)

    ner._save_location_maps(
        {"Alice": {"Paris": 1}},
        {"Alice": {"Paris": ["Alice mentioned Paris."]}},
        output_service,
        location_mentions_per_speaker={
            "Alice": {
                "Paris": [
                    {
                        "text": "Alice mentioned Paris.",
                        "segment_index": 7,
                        "start": 42.0,
                    }
                ]
            }
        },
    )

    raw = (tmp_path / "ner" / "ner-locations.json").read_text(encoding="utf-8")
    payload = ast.literal_eval(raw)
    assert payload["Alice"][0]["segment_index"] == 7
    assert payload["Alice"][0]["start"] == 42.0
    assert payload["Alice"][0]["sentence"] == "Alice mentioned Paris."
