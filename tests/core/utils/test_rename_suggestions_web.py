"""Web query builder and HTML parsing for rename suggestions."""

from __future__ import annotations

from transcriptx.core.utils.rename.suggestions.transcript_cues import looks_like_public_event
from transcriptx.core.utils.rename.suggestions.web import (
    build_web_query,
    fetch_web_cue,
    parse_dates_from_html,
)


def test_web_query_never_includes_transcript_secret() -> None:
    query = build_web_query(
        title="Product Launch",
        filename="voice_memo.m4a",
    )
    assert "SECRET_PHRASE_XYZ" not in query
    assert len(query) <= 120
    assert not looks_like_public_event("voice_memo.m4a", [{"text": "SECRET_PHRASE_XYZ"}])


def test_public_filename_adds_webinar_to_query() -> None:
    query = build_web_query(title="Acme Launch", filename="zoom_webinar_01.mp3")
    assert "webinar" in query.lower()


def test_parse_dates_from_fixture_html() -> None:
    html = """
    <a class="result__a">Acme webinar recap</a>
    <a class="result__snippet">Held March 12, 2026 online.</a>
    """
    parsed, detail, _title = parse_dates_from_html(html)
    assert parsed is not None
    assert parsed.year == 2026
    assert "Web result" in detail


def test_fetch_web_cue_returns_none_on_http_error(monkeypatch) -> None:
    class _Resp:
        status_code = 500
        text = ""

    def _get(*_a, **_k):
        return _Resp()

    monkeypatch.setattr(
        "transcriptx.core.utils.rename.suggestions.web.httpx.get",
        _get,
    )
    assert fetch_web_cue("acme webinar") is None
