"""Read-only Twenty CRM people lookup for speaker-name evidence/gates.

Opt-in. API key stays in env (``TWENTY_API_KEY`` / ``TWENTY_BASE_URL``), same
names as Paperful. Never writes People records.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

import httpx

from transcriptx.core.speaker_profiles.identify.settings import IdentifySettings
from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
from transcriptx.io.atomic_json import write_json_atomic

CACHE_NAME = "twenty_people.v1.json"
CACHE_SCHEMA = "transcriptx.twenty_people.v1"
DEFAULT_TTL_SECONDS = 24 * 60 * 60
Sender = Callable[
    [str, str, dict[str, str], dict[str, str], dict[str, Any] | None], Any
]


def twenty_api_key() -> str:
    return (os.environ.get("TWENTY_API_KEY") or "").strip()


def twenty_base_url(settings: IdentifySettings | None = None) -> str:
    env = (os.environ.get("TWENTY_BASE_URL") or "").strip()
    cfg = ""
    if settings is not None:
        cfg = str(settings.twenty_base_url or "").strip()
    return (env or cfg).rstrip("/")


def twenty_ready(settings: IdentifySettings | None = None) -> bool:
    if settings is None:
        from transcriptx.core.speaker_profiles.identify.settings import (
            load_identify_settings,
        )

        settings = load_identify_settings()
    if not settings.twenty_enabled:
        return False
    return bool(twenty_api_key() and twenty_base_url(settings))


@dataclass
class PersonHit:
    twenty_id: str
    first_name: str = ""
    last_name: str = ""
    display_name: str = ""

    def identity_name(self) -> str:
        return (
            self.display_name
            or " ".join(p for p in (self.first_name, self.last_name) if p).strip()
        )


@dataclass
class TwentyPeopleIndex:
    people: list[PersonHit] = field(default_factory=list)
    fetched_at: str = ""
    error: str | None = None

    def unique_display(self, name: str) -> PersonHit | None:
        key = _fold(name)
        if not key:
            return None
        hits = [p for p in self.people if _fold(p.identity_name()) == key]
        if len(hits) == 1:
            return hits[0]
        first, last = _split_name(name)
        return unique_match(self.people, last, first)


def _fold(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _split_name(name: str) -> tuple[str, str]:
    parts = [p for p in re.split(r"\s+", (name or "").strip()) if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[-1]


def names_match(hit: PersonHit, last: str, first: str = "") -> bool:
    hit_last = _fold(hit.last_name)
    want_last = _fold(last)
    if want_last:
        if not hit_last or hit_last != want_last:
            return False
    want_first = _fold(first)
    if not want_first:
        return True
    hit_first = _fold(hit.first_name)
    if not hit_first:
        return False
    if hit_first == want_first:
        return True
    if len(want_first) == 1:
        return hit_first.startswith(want_first)
    if len(hit_first) == 1:
        return want_first.startswith(hit_first)
    return hit_first.startswith(want_first) or want_first.startswith(hit_first)


def unique_match(hits: list[PersonHit], last: str, first: str = "") -> PersonHit | None:
    matched = [h for h in hits if names_match(h, last, first)]
    if len(matched) != 1:
        return None
    return matched[0]


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {twenty_api_key()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("firstName", "lastName", "name", "displayName"):
            if value.get(key):
                return str(value.get(key) or "").strip()
    return str(value).strip()


def parse_person(row: dict[str, Any]) -> PersonHit | None:
    if not isinstance(row, dict):
        return None
    name = row.get("name") if isinstance(row.get("name"), dict) else {}
    first = _text(name.get("firstName") if name else row.get("firstName"))
    last = _text(name.get("lastName") if name else row.get("lastName"))
    display = _text(row.get("displayName")) or " ".join(p for p in (first, last) if p)
    pid = str(row.get("id") or "").strip()
    if not pid and not last:
        return None
    return PersonHit(
        twenty_id=pid,
        first_name=first,
        last_name=last,
        display_name=display,
    )


def _people_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    if not isinstance(payload, dict):
        return []
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    people = data.get("people")
    if isinstance(people, list):
        return [p for p in people if isinstance(p, dict)]
    if isinstance(people, dict) and isinstance(people.get("edges"), list):
        rows = []
        for edge in people["edges"]:
            node = edge.get("node") if isinstance(edge, dict) else None
            if isinstance(node, dict):
                rows.append(node)
        return rows
    return []


def _default_send(
    method: str,
    url: str,
    headers: dict[str, str],
    params: dict[str, str],
    body: dict[str, Any] | None,
) -> Any:
    with httpx.Client(timeout=20) as client:
        resp = client.request(
            method, url, headers=headers, params=params or None, json=body
        )
        resp.raise_for_status()
        if not resp.content:
            return {}
        return resp.json()


def twenty_request(
    settings: IdentifySettings,
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    sender: Sender | None = None,
) -> Any:
    base = twenty_base_url(settings)
    url = urljoin(base + "/", path.lstrip("/"))
    call = sender or _default_send
    return call(method, url, _headers(), params or {}, None)


def search_people(
    settings: IdentifySettings,
    *,
    last_name: str,
    first_name: str = "",
    sender: Sender | None = None,
) -> list[PersonHit]:
    last = (last_name or "").strip()
    if not last:
        return []
    filt = 'name.lastName[ilike]:"%s"' % last.replace('"', "")
    payload = twenty_request(
        settings,
        "GET",
        "rest/people",
        params={"filter": filt, "limit": "20"},
        sender=sender,
    )
    hits = [p for p in (parse_person(row) for row in _people_list(payload)) if p]
    first = (first_name or "").strip()
    if first:
        tight = [h for h in hits if names_match(h, last, first)]
        if tight:
            return tight
    return hits


def cache_path(*, root: Path | None = None) -> Path:
    base = Path(root) if root is not None else speaker_profiles_dir()
    return base / ".cache" / "identify" / CACHE_NAME


def _index_from_payload(raw: dict[str, Any]) -> TwentyPeopleIndex:
    people: list[PersonHit] = []
    for row in raw.get("people") or []:
        if not isinstance(row, dict):
            continue
        hit = parse_person(
            {
                "id": row.get("id"),
                "name": {
                    "firstName": row.get("first_name"),
                    "lastName": row.get("last_name"),
                },
                "displayName": row.get("display_name"),
            }
        )
        if hit:
            people.append(hit)
    return TwentyPeopleIndex(
        people=people,
        fetched_at=str(raw.get("fetched_at") or ""),
        error=str(raw["error"]) if raw.get("error") else None,
    )


def load_people_cache(*, root: Path | None = None) -> TwentyPeopleIndex | None:
    path = cache_path(root=root)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or raw.get("schema_id") != CACHE_SCHEMA:
        return None
    return _index_from_payload(raw)


def cache_is_fresh(
    index: TwentyPeopleIndex | None, *, ttl_seconds: int = DEFAULT_TTL_SECONDS
) -> bool:
    if index is None or not index.fetched_at or index.error:
        return False
    try:
        fetched = datetime.fromisoformat(index.fetched_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - fetched).total_seconds()
    return age <= ttl_seconds


def write_people_cache(index: TwentyPeopleIndex, *, root: Path | None = None) -> Path:
    path = cache_path(root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_id": CACHE_SCHEMA,
        "fetched_at": index.fetched_at,
        "error": index.error,
        "people": [
            {
                "id": p.twenty_id,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "display_name": p.identity_name(),
            }
            for p in index.people
        ],
    }
    write_json_atomic(path, payload, indent=2)
    return path


def fetch_people_snapshot(
    settings: IdentifySettings,
    *,
    sender: Sender | None = None,
    limit: int = 200,
) -> TwentyPeopleIndex:
    people: list[PersonHit] = []
    try:
        payload = twenty_request(
            settings,
            "GET",
            "rest/people",
            params={"limit": str(max(1, min(int(limit), 200)))},
            sender=sender,
        )
        for row in _people_list(payload):
            hit = parse_person(row)
            if hit:
                people.append(hit)
        return TwentyPeopleIndex(
            people=people,
            fetched_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
    except (httpx.HTTPError, OSError, ValueError) as exc:
        return TwentyPeopleIndex(
            people=[],
            fetched_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            error=str(exc),
        )


def refresh_people_cache(
    settings: IdentifySettings,
    *,
    root: Path | None = None,
    sender: Sender | None = None,
) -> TwentyPeopleIndex:
    index = fetch_people_snapshot(settings, sender=sender)
    write_people_cache(index, root=root)
    return index


def get_people_index(
    settings: IdentifySettings | None = None,
    *,
    root: Path | None = None,
    force_refresh: bool = False,
    sender: Sender | None = None,
) -> TwentyPeopleIndex | None:
    if settings is None:
        from transcriptx.core.speaker_profiles.identify.settings import (
            load_identify_settings,
        )

        settings = load_identify_settings()
    if not twenty_ready(settings):
        return None
    cached = load_people_cache(root=root)
    if not force_refresh and cache_is_fresh(cached):
        return cached
    try:
        return refresh_people_cache(settings, root=root, sender=sender)
    except (httpx.HTTPError, OSError, ValueError):
        return cached


def unique_crm_person(name: str, index: TwentyPeopleIndex | None) -> PersonHit | None:
    if index is None or not name:
        return None
    return index.unique_display(name)
