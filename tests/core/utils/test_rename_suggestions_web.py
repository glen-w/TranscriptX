"""Web query builder and HTML parsing for rename suggestions."""

from __future__ import annotations

from transcriptx.core.utils.rename.suggestions.transcript_cues import (
    looks_like_public_event,
)
from transcriptx.core.utils.rename.suggestions.web import (
    build_web_query,
    build_youtube_web_query,
    fetch_web_cue,
    fetch_web_cue_from_title,
    fetch_youtube_api_cue,
    parse_dates_from_html,
    parse_youtube_published_at,
)


def test_web_query_never_includes_transcript_secret() -> None:
    query = build_web_query(
        title="Product Launch",
        filename="voice_memo.m4a",
    )
    assert "SECRET_PHRASE_XYZ" not in query
    assert len(query) <= 120
    assert not looks_like_public_event(
        "voice_memo.m4a", [{"text": "SECRET_PHRASE_XYZ"}]
    )


def test_public_filename_adds_webinar_to_query() -> None:
    query = build_web_query(title="Acme Launch", filename="zoom_webinar_01.mp3")
    assert "webinar" in query.lower()


def test_youtube_query_uses_site_operator() -> None:
    query = build_youtube_web_query(
        title="Youth Voices High Seas",
        filename="youth_voices.json",
    )
    assert "site:youtube.com" in query
    assert "Youth" in query


def test_fetch_web_cue_from_title_tries_youtube_then_general(monkeypatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_YOUTUBE_API_KEY", raising=False)
    calls: list[str] = []

    class _Resp:
        status_code = 200
        text = ""

    def _get(_url, *, params=None, **_k):
        q = (params or {}).get("q", "")
        calls.append(q)
        if "site:youtube.com" in q:
            return _Resp()
        html = """
        <a class="result__a">Acme webinar recap</a>
        <a class="result__snippet">Held March 12, 2026 online.</a>
        """
        return type("_R", (), {"status_code": 200, "text": html})()

    monkeypatch.setattr(
        "transcriptx.core.utils.rename.suggestions.web.httpx.get",
        _get,
    )
    cue = fetch_web_cue_from_title(title="Acme Launch", filename="zoom.mp3")
    assert cue is not None
    assert cue.event_date is not None
    assert calls[0].endswith("site:youtube.com") or "site:youtube.com" in calls[0]
    assert len(calls) >= 2


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


def test_parse_youtube_published_at() -> None:
    parsed = parse_youtube_published_at("2026-03-12T15:04:05Z")
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 3
    assert parsed.day == 12


def test_fetch_youtube_api_cue_uses_search_then_videos() -> None:
    calls: list[str] = []

    class _Resp:
        def __init__(self, payload, status=200):
            self.status_code = status
            self._payload = payload

        def json(self):
            return self._payload

    def _get(url, *, params=None, **_k):
        calls.append(url)
        if url.endswith("/search"):
            assert "SECRET" not in str(params.get("q"))
            return _Resp(
                {
                    "items": [
                        {
                            "id": {"videoId": "abc123"},
                            "snippet": {"title": "Acme webinar"},
                        }
                    ]
                }
            )
        return _Resp(
            {
                "items": [
                    {
                        "id": "abc123",
                        "snippet": {
                            "title": "Acme webinar",
                            "publishedAt": "2026-03-12T15:04:05Z",
                        },
                    }
                ]
            }
        )

    cue = fetch_youtube_api_cue("Acme webinar", api_key="test-key", http_get=_get)
    assert cue is not None
    assert cue.event_date is not None
    assert cue.event_date.day == 12
    assert "YouTube Data API" in cue.detail
    assert len(calls) == 2


def test_fetch_web_cue_from_title_prefers_youtube_api(monkeypatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_YOUTUBE_API_KEY", "k")

    class _Cue:
        event_date = None

    def _api(query, *, api_key, timeout=8.0, **_k):
        assert query == "Acme Launch"
        assert api_key == "k"
        from datetime import date

        from transcriptx.core.utils.rename.suggestions.models import RawRenameCue

        return RawRenameCue(
            basis="web",
            confidence="likely",
            detail="YouTube Data API: Acme Launch",
            event_date=date(2026, 3, 12),
            title="Acme Launch",
            _priority=2,
        )

    monkeypatch.setattr(
        "transcriptx.core.utils.rename.suggestions.web.fetch_youtube_api_cue",
        _api,
    )
    ddg_calls: list[str] = []
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.suggestions.web.fetch_web_cue",
        lambda q, **_k: ddg_calls.append(q) or None,
    )
    cue = fetch_web_cue_from_title(title="Acme Launch", filename="zoom.mp3")
    assert cue is not None
    assert "YouTube Data API" in cue.detail
    assert ddg_calls == []


def test_fetch_web_cue_from_title_falls_back_to_ddg_on_api_failure(monkeypatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_YOUTUBE_API_KEY", "secret-youtube-key")
    api_calls: list[str] = []

    def _api(query, *, api_key, timeout=8.0, **_k):
        api_calls.append(query)
        assert api_key == "secret-youtube-key"
        assert "SECRET" not in query
        return None

    html = """
    <a class="result__a">Acme webinar recap</a>
    <a class="result__snippet">Held March 12, 2026 online.</a>
    """

    def _ddg(q, **_k):
        from datetime import date

        from transcriptx.core.utils.rename.suggestions.models import RawRenameCue

        assert "secret-youtube-key" not in q
        return RawRenameCue(
            basis="web",
            confidence="likely",
            detail="Web result: Acme webinar recap",
            event_date=date(2026, 3, 12),
            title="Acme webinar recap",
            _priority=2,
        )

    monkeypatch.setattr(
        "transcriptx.core.utils.rename.suggestions.web.fetch_youtube_api_cue",
        _api,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.suggestions.web.fetch_web_cue",
        _ddg,
    )
    cue = fetch_web_cue_from_title(title="Acme Launch", filename="zoom.mp3")
    assert cue is not None
    assert "YouTube Data API" not in cue.detail
    assert api_calls == ["Acme Launch"]


def test_fetch_youtube_api_cue_http_error_returns_none_without_key() -> None:
    import httpx

    def _get(url, *, params=None, **_k):
        raise httpx.HTTPError("boom secret-youtube-key")

    cue = fetch_youtube_api_cue(
        "Acme Launch", api_key="secret-youtube-key", http_get=_get
    )
    assert cue is None


def test_fetch_youtube_api_cue_empty_items_returns_none() -> None:
    class _Resp:
        status_code = 403

        def json(self):
            return {"error": {"message": "quota"}}

    cue = fetch_youtube_api_cue(
        "Acme Launch", api_key="secret-youtube-key", http_get=lambda *_a, **_k: _Resp()
    )
    assert cue is None
