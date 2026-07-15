"""Tests for artifact file preview rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.blocks.implementations import data as data_mod
from transcriptx.web.models.artifact import Artifact


def _artifact(**kwargs) -> Artifact:
    base = dict(
        id="a1",
        kind="other",
        module="stats",
        scope="global",
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path="stats/charts/global/chart.png",
        bytes=8,
        mtime="2024-01-01T00:00:00Z",
        mime="image/png",
        tags=[],
        title="chart",
    )
    base.update(kwargs)
    return Artifact.from_dict(base)


class _DummySt:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def caption(self, *args, **kwargs):
        self.calls.append(("caption", args, kwargs))

    def image(self, *args, **kwargs):
        self.calls.append(("image", args, kwargs))

    def iframe(self, *args, **kwargs):
        self.calls.append(("iframe", args, kwargs))

    def write(self, *args, **kwargs):
        self.calls.append(("write", args, kwargs))

    def info(self, *args, **kwargs):
        self.calls.append(("info", args, kwargs))

    def dataframe(self, *args, **kwargs):
        self.calls.append(("dataframe", args, kwargs))

    def json(self, *args, **kwargs):
        self.calls.append(("json", args, kwargs))

    def markdown(self, *args, **kwargs):
        self.calls.append(("markdown", args, kwargs))

    def text_area(self, *args, **kwargs):
        self.calls.append(("text_area", args, kwargs))


@pytest.mark.unit
def test_png_chart_preview_uses_image_not_read_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    png = tmp_path / "chart.png"
    # PNG magic bytes — would crash utf-8 read_text()
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)

    dummy = _DummySt()
    monkeypatch.setattr(data_mod, "st", dummy)

    selected = _artifact(
        kind="chart_static",
        rel_path="chart.png",
        mime="image/png",
    )
    data_mod.render_artifact_file_preview(tmp_path, selected)

    assert any(name == "image" for name, *_ in dummy.calls)
    assert not any(name == "write" for name, *_ in dummy.calls)


@pytest.mark.unit
def test_binary_other_preview_does_not_decode_as_utf8(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blob = tmp_path / "payload.bin"
    blob.write_bytes(b"\x89\xfe\x00\x01")

    dummy = _DummySt()
    monkeypatch.setattr(data_mod, "st", dummy)

    selected = _artifact(
        kind="other",
        rel_path="payload.bin",
        mime="application/octet-stream",
    )
    data_mod.render_artifact_file_preview(tmp_path, selected)

    assert any(name == "info" for name, *_ in dummy.calls)
    assert not any(name == "write" for name, *_ in dummy.calls)
