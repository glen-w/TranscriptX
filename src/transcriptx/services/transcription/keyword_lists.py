"""Named keyword lists for Granite Speech keyword biasing.

Stored under ``{PROFILES_DIR}/keyword_lists/<name>.json`` via ProfileManager.
Never stores secrets. Cap is 2000 terms (IBM Granite Speech 5.0 limit).
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Sequence

from transcriptx.core.utils.profile_manager import ProfileManager

MODULE_ID = "keyword_lists"
SCHEMA_VERSION = 1
MAX_KEYWORDS = 2000

_SECRET_KEYS = frozenset(
    {
        "hf_token",
        "HF_TOKEN",
        "token",
        "api_key",
        "openai_api_key",
        "OPENAI_API_KEY",
    }
)


class KeywordListError(ValueError):
    """Invalid keyword-list payload."""


def _manager(profiles_dir=None) -> ProfileManager:
    return ProfileManager(profiles_dir=profiles_dir)


def list_lists(*, profiles_dir=None) -> list[str]:
    return _manager(profiles_dir).list_profiles(MODULE_ID)


def delete_list(name: str, *, profiles_dir=None) -> bool:
    return _manager(profiles_dir).delete_profile(MODULE_ID, name)


def normalize_keywords(
    terms: Iterable[Any],
    *,
    cap: int = MAX_KEYWORDS,
) -> tuple[tuple[str, ...], str | None]:
    """Strip, drop empty, de-dupe (order-preserving), cap at ``cap``.

    Returns ``(keywords, warning)``. Warning is set when terms were truncated.
    """
    seen: set[str] = set()
    out: list[str] = []
    truncated = False
    for raw in terms:
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        if text in seen:
            continue
        if len(out) >= cap:
            truncated = True
            break
        seen.add(text)
        out.append(text)
    warning = None
    if truncated:
        warning = f"Keyword list truncated to {cap} terms (Granite Speech limit)."
    return tuple(out), warning


def parse_keyword_text(text: str) -> list[str]:
    """Parse a textarea: JSON array, JSON object with ``keywords``, or lines/commas."""
    stripped = (text or "").strip()
    if not stripped:
        return []
    if stripped[0] in "[{":
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            return [str(item) for item in data]
        if isinstance(data, dict) and isinstance(data.get("keywords"), list):
            return [str(item) for item in data["keywords"]]
    terms: list[str] = []
    for line in stripped.splitlines():
        if "," in line and not line.strip().startswith("#"):
            terms.extend(part.strip() for part in line.split(","))
        else:
            terms.append(line.strip())
    return terms


def _validate_config(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise KeywordListError("Keyword list config must be an object")
    for key in _SECRET_KEYS:
        if key in data:
            raise KeywordListError(f"Keyword list must not contain secret key {key!r}")
    version = data.get("schema_version", SCHEMA_VERSION)
    try:
        version_int = int(version)
    except (TypeError, ValueError) as exc:
        raise KeywordListError("Invalid schema_version") from exc
    if version_int != SCHEMA_VERSION:
        raise KeywordListError(
            f"Unsupported schema_version {version_int} (expected {SCHEMA_VERSION})"
        )
    raw = data.get("keywords", [])
    if not isinstance(raw, list):
        raise KeywordListError("keywords must be a list")
    keywords, _warning = normalize_keywords(raw)
    return {"schema_version": SCHEMA_VERSION, "keywords": list(keywords)}


def save_list(
    name: str,
    keywords: Sequence[str],
    *,
    description: str = "",
    overwrite: bool = True,
    profiles_dir=None,
) -> bool:
    normalized, _warning = normalize_keywords(keywords)
    config = {"schema_version": SCHEMA_VERSION, "keywords": list(normalized)}
    return _manager(profiles_dir).save_profile(
        MODULE_ID,
        name,
        config,
        description=description or f"Keyword list: {name}",
        overwrite=overwrite,
    )


def load_list(name: str, *, profiles_dir=None) -> tuple[str, ...]:
    payload = _manager(profiles_dir).load_profile(MODULE_ID, name)
    if payload is None:
        raise KeywordListError(f"Keyword list {name!r} not found or invalid")
    config = payload.get("config")
    if not isinstance(config, dict):
        raise KeywordListError(f"Keyword list {name!r} has no config object")
    validated = _validate_config(config)
    keywords, _warning = normalize_keywords(validated["keywords"])
    return keywords


def export_list_json(name: str, *, profiles_dir=None) -> str:
    keywords = load_list(name, profiles_dir=profiles_dir)
    return (
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "name": name,
                "keywords": list(keywords),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


def export_list_txt(name: str, *, profiles_dir=None) -> str:
    keywords = load_list(name, profiles_dir=profiles_dir)
    return "\n".join(keywords) + ("\n" if keywords else "")


def import_list(
    name: str,
    text: str,
    *,
    overwrite: bool = True,
    profiles_dir=None,
) -> tuple[str, ...]:
    keywords, _warning = normalize_keywords(parse_keyword_text(text))
    if not save_list(name, keywords, overwrite=overwrite, profiles_dir=profiles_dir):
        raise KeywordListError(f"Could not save keyword list {name!r}")
    return keywords


def resolve_run_keywords(
    *,
    enabled: bool,
    list_name: str | None = None,
    extra: str = "",
    profiles_dir=None,
) -> tuple[tuple[str, ...], str | None]:
    """Combine a saved list plus extra terms when biasing is on.

    Returns ``(keywords, warning)``. Empty when ``enabled`` is false.
    """
    if not enabled:
        return (), None
    terms: list[str] = []
    warning_parts: list[str] = []
    name = (list_name or "").strip()
    if name and name not in {"—", "-"}:
        try:
            terms.extend(load_list(name, profiles_dir=profiles_dir))
        except KeywordListError as exc:
            warning_parts.append(str(exc))
    terms.extend(parse_keyword_text(extra))
    keywords, cap_warning = normalize_keywords(terms)
    if cap_warning:
        warning_parts.append(cap_warning)
    warning = " ".join(warning_parts) if warning_parts else None
    return keywords, warning
