"""Mirror the navigation context into the URL so refresh / bookmark survive.

Scope (W1.1 of the 2026-11 GUI hardening wave): ``page``, ``subject_type``,
``subject_id`` and ``run_id`` only. One-shot navigation keys, filters and
widget state stay out of the URL. Hydration happens once per browser session
(before prerequisites are evaluated); mirroring happens after the sidebar has
had its chance to hydrate pickers, so the URL reflects what the user sees.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from transcriptx.web.navigation import PAGE_SPECS, migrate_legacy_page_key
from transcriptx.web.state import (
    PAGE_KEY,
    RUN_ID_KEY,
    SUBJECT_ID_KEY,
    SUBJECT_TYPE_KEY,
    apply_subject_context,
)

URL_PAGE = "page"
URL_SUBJECT_TYPE = "subject_type"
URL_SUBJECT_ID = "subject_id"
URL_RUN_ID = "run_id"
URL_KEYS: tuple[str, ...] = (URL_PAGE, URL_SUBJECT_TYPE, URL_SUBJECT_ID, URL_RUN_ID)

# Session flag: hydrate from the URL only on the first run of a session.
URL_HYDRATED_KEY = "_tx_url_hydrated"

_KNOWN_PAGE_KEYS: frozenset[str] = frozenset(spec.key for spec in PAGE_SPECS)
_SUBJECT_TYPES = ("transcript", "group")


def _first(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()


def hydrate_session_from_url(
    session_state: MutableMapping[str, Any], query_params: Mapping[str, Any]
) -> bool:
    """Apply URL context to a fresh session. Returns True when anything changed.

    Idempotent per session via ``URL_HYDRATED_KEY``. Unknown page keys are
    ignored (router fallbacks still apply to pages whose prerequisites are
    not met once the library is scanned).
    """
    if session_state.get(URL_HYDRATED_KEY):
        return False
    session_state[URL_HYDRATED_KEY] = True

    changed = False
    page = _first(query_params.get(URL_PAGE))
    if page:
        page, _hint = migrate_legacy_page_key(page)
        if page in _KNOWN_PAGE_KEYS:
            session_state[PAGE_KEY] = page
            changed = True

    subject_type = _first(query_params.get(URL_SUBJECT_TYPE)).lower()
    subject_id = _first(query_params.get(URL_SUBJECT_ID))
    run_id = _first(query_params.get(URL_RUN_ID)) or None
    if subject_type in _SUBJECT_TYPES and subject_id:
        apply_subject_context(
            session_state,
            subject_type=subject_type,  # type: ignore[arg-type]
            subject_id=subject_id,
            run_id=run_id,
        )
        changed = True
    return changed


def desired_url_params(session_state: Mapping[str, Any]) -> dict[str, str]:
    """URL representation of the current navigation context."""
    out: dict[str, str] = {}
    page = session_state.get(PAGE_KEY)
    if isinstance(page, str) and page in _KNOWN_PAGE_KEYS and page != "Home":
        out[URL_PAGE] = page
    subject_type = session_state.get(SUBJECT_TYPE_KEY)
    subject_id = session_state.get(SUBJECT_ID_KEY)
    if subject_type in _SUBJECT_TYPES and subject_id:
        out[URL_SUBJECT_TYPE] = str(subject_type)
        out[URL_SUBJECT_ID] = str(subject_id)
        run_id = session_state.get(RUN_ID_KEY)
        if run_id:
            out[URL_RUN_ID] = str(run_id)
    return out


def sync_url_from_session(
    session_state: Mapping[str, Any], query_params: MutableMapping[str, Any]
) -> bool:
    """Write the navigation context into ``query_params`` (only on change).

    Only the keys in ``URL_KEYS`` are touched; other query params (e.g. the
    ``perf_scenario`` probe) are preserved. Returns True when a write happened.
    """
    desired = desired_url_params(session_state)
    current = {k: _first(query_params.get(k)) for k in URL_KEYS}
    changed = False
    for key in URL_KEYS:
        want = desired.get(key, "")
        if want == current.get(key, ""):
            continue
        changed = True
        if want:
            query_params[key] = want
        else:
            try:
                del query_params[key]
            except KeyError:
                pass
    return changed
