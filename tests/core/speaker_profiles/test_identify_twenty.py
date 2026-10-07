"""Read-only Twenty CRM people lookup (mocked HTTP)."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.speaker_profiles.identify.settings import IdentifySettings
from transcriptx.core.speaker_profiles.identify.suggestions.deterministic import (
    build_deterministic_options,
)
from transcriptx.core.speaker_profiles.identify.twenty import (
    PersonHit,
    names_match,
    parse_person,
    refresh_people_cache,
    unique_match,
    unique_crm_person,
    twenty_ready,
)


def _people_payload(people: list[dict]) -> dict:
    return {"data": {"people": people}}


@pytest.mark.unit
def test_unique_match_fails_closed_on_ambiguous() -> None:
    hits = [
        PersonHit(twenty_id="1", first_name="Ada", last_name="Lovelace"),
        PersonHit(twenty_id="2", first_name="Ann", last_name="Lovelace"),
    ]
    assert unique_match(hits, "Lovelace") is None
    assert unique_match(hits, "Lovelace", "Ada") is not None
    assert names_match(hits[0], "Lovelace", "Ada")


@pytest.mark.unit
def test_twenty_ready_needs_key_and_url(monkeypatch) -> None:
    monkeypatch.delenv("TWENTY_API_KEY", raising=False)
    monkeypatch.delenv("TWENTY_BASE_URL", raising=False)
    settings = IdentifySettings(twenty_enabled=True, twenty_role="evidence")
    assert twenty_ready(settings) is False
    monkeypatch.setenv("TWENTY_API_KEY", "test-key")
    monkeypatch.setenv("TWENTY_BASE_URL", "https://twenty.example")
    assert twenty_ready(settings) is True


@pytest.mark.unit
def test_refresh_snapshot_and_crm_option(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TWENTY_API_KEY", "test-key")
    monkeypatch.setenv("TWENTY_BASE_URL", "https://twenty.example")
    settings = IdentifySettings(
        twenty_enabled=True,
        twenty_role="evidence",
        twenty_base_url="https://twenty.example",
    )

    def sender(method, url, headers, params, body):
        assert "Bearer test-key" in headers.get("Authorization", "")
        return _people_payload(
            [
                {
                    "id": "abc",
                    "name": {"firstName": "Maya", "lastName": "Chen"},
                    "displayName": "Maya Chen",
                }
            ]
        )

    index = refresh_people_cache(settings, root=tmp_path, sender=sender)
    assert index.error is None
    assert unique_crm_person("Maya Chen", index) is not None

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.identify.settings.load_identify_settings",
        lambda **kwargs: settings,
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.identify.twenty.get_people_index",
        lambda settings=None, **kwargs: index,
    )

    segments = [
        {"speaker": "SPEAKER_00", "text": "Hi, I'm Maya."},
        {"speaker": "SPEAKER_01", "text": "Welcome."},
    ]
    roster = ()
    opts = build_deterministic_options(segments, roster)
    assert any(
        o.basis == "crm" and o.display_name == "Maya Chen"
        for o in opts.get("SPEAKER_00", ())
    )


@pytest.mark.unit
def test_parse_person_nested_name() -> None:
    hit = parse_person(
        {"id": "1", "name": {"firstName": "Ada", "lastName": "Lovelace"}}
    )
    assert hit is not None
    assert hit.identity_name() == "Ada Lovelace"
