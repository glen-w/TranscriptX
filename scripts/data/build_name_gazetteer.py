#!/usr/bin/env python3
"""Rebuild bundled given/surname gazetteer JSON (maintainer script)."""

from __future__ import annotations

import csv
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "src" / "transcriptx" / "preprocessing" / "names"

FORENAMES_URL = (
    "https://github.com/sigpwned/popular-names-by-country-dataset/"
    "releases/download/v1.2/common-forenames.txt"
)
SURNAMES_URL = (
    "https://github.com/sigpwned/popular-names-by-country-dataset/"
    "releases/download/v1.2/common-surnames.txt"
)
BABY_URL = (
    "https://raw.githubusercontent.com/hadley/data-baby-names/master/" "baby-names.csv"
)
CENSUS_URL = (
    "https://raw.githubusercontent.com/fivethirtyeight/data/master/"
    "most-common-name/surnames.csv"
)

EXTRAS_GIVEN = (
    "Maya",
    "Nicola",
    "Quentin",
    "Quinton",
    "Alex",
    "Jane",
    "Jordan",
    "Cara",
    "Sam",
    "Wren",
    "Glen",
    "Jonas",
    "Yanko",
)


def _norm(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    letters = text.replace("'", "").replace("-", "")
    if not letters.isalpha():
        return ""
    if text.isupper() or text.islower():
        return text[:1].upper() + text[1:].lower()
    return text[:1].upper() + text[1:]


def _fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as resp:  # nosec B310
        return resp.read().decode("utf-8", errors="replace")


def main() -> None:
    given: set[str] = set()
    surnames: set[str] = set()
    for line in _fetch(FORENAMES_URL).splitlines():
        name = _norm(line)
        if name:
            given.add(name)
    for line in _fetch(SURNAMES_URL).splitlines():
        name = _norm(line)
        if name:
            surnames.add(name)
    for row in csv.DictReader(_fetch(BABY_URL).splitlines()):
        name = _norm(row.get("name") or "")
        if name:
            given.add(name)
    for row in csv.DictReader(_fetch(CENSUS_URL).splitlines()):
        name = _norm((row.get("name") or "").title())
        if name:
            surnames.add(name)
    given.update(EXTRAS_GIVEN)
    OUT.mkdir(parents=True, exist_ok=True)
    given_list = sorted(given, key=lambda x: x.casefold())
    sur_list = sorted(surnames, key=lambda x: x.casefold())
    (OUT / "given_names.json").write_text(
        json.dumps(given_list, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUT / "surnames.json").write_text(
        json.dumps(sur_list, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(given_list)} given names, {len(sur_list)} surnames")


if __name__ == "__main__":
    main()
