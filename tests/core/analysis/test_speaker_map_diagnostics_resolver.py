"""Speaker-map diagnostics must call the resolver as an instance method."""

from __future__ import annotations

from pathlib import Path

import pytest

_SRC = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "transcriptx"
    / "core"
    / "analysis"
    / "speaker_map_diagnostics"
    / "__init__.py"
)


@pytest.mark.unit
def test_analyze_instantiates_resolver_before_load_mapping() -> None:
    src = _SRC.read_text(encoding="utf-8")
    assert "SpeakerMapResolver().load_mapping(self._transcript_path)" in src
    assert "SpeakerMapResolver.load_mapping(" not in src
