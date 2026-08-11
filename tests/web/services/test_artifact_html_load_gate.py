"""Artifact HTML load gating for Charts performance."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from transcriptx.web.services.artifact_service import ArtifactService


def test_load_html_artifact_skips_read_when_over_max(
    tmp_path: Path, monkeypatch
) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    html = run_root / "big.html"
    html.write_text("x" * 1000, encoding="utf-8")
    artifact = SimpleNamespace(kind="chart_dynamic", rel_path="big.html", id="c1")

    monkeypatch.setattr(
        ArtifactService,
        "resolve_artifact_source_path",
        staticmethod(lambda _root, _art: html),
    )

    read_calls: list[str] = []
    original_read = Path.read_text

    def _tracking_read(self, *args, **kwargs):
        read_calls.append(str(self))
        return original_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _tracking_read)

    payload = ArtifactService.load_html_artifact(
        run_root, artifact, max_read_bytes=100
    )
    assert payload is not None
    assert payload["truncated"] is True
    assert payload["content"] is None
    assert payload["bytes"] == 1000
    assert read_calls == []

    payload_ok = ArtifactService.load_html_artifact(
        run_root, artifact, max_read_bytes=5000
    )
    assert payload_ok is not None
    assert payload_ok["truncated"] is False
    assert payload_ok["content"] == "x" * 1000
    assert read_calls == [str(html)]


def test_charts_gallery_card_source_avoids_iframe_for_dynamic() -> None:
    source = Path(
        "src/transcriptx/web/page_modules/charts.py"
    ).read_text(encoding="utf-8")
    # Gallery path must not load HTML or iframe dynamic charts inline.
    card_fn_start = source.index("def _render_chart_gallery_card")
    card_fn_end = source.index("def _render_chart_card_grid")
    card_body = source[card_fn_start:card_fn_end]
    assert "st.iframe" not in card_body
    assert "load_html_artifact" not in card_body
    assert "open full screen to view" in card_body


def test_charts_fullscreen_uses_max_read_bytes_gate() -> None:
    source = Path(
        "src/transcriptx/web/page_modules/charts.py"
    ).read_text(encoding="utf-8")
    assert "max_read_bytes=MAX_FULLSCREEN_HTML_BYTES" in source
    assert 'html_payload.get("truncated")' in source
