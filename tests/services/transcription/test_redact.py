"""Tests for secret redaction."""

from __future__ import annotations

import pytest

from transcriptx.services.transcription.redact import redact_secret


@pytest.mark.unit
def test_redact_secret_replaces_token():
    text = "failed with token hf_abc123 in output"
    result = redact_secret(text, ["hf_abc123"])
    assert "hf_abc123" not in result
    assert "***" in result


@pytest.mark.unit
def test_redact_secret_skips_empty():
    assert redact_secret("unchanged", [""]) == "unchanged"


@pytest.mark.unit
def test_tail_lines_limits_output():
    from transcriptx.services.transcription.redact import tail_lines

    text = "\n".join(f"line{i}" for i in range(30))
    tail = tail_lines(text, max_lines=5)
    assert len(tail) == 5
    assert tail[-1] == "line29"
