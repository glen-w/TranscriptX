"""Canonical JSON hashing for emotion-family fingerprints and row checksums."""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

CANONICAL_JSON_HASH_V1 = "canonical_json_hash_v1"


def quantize_float_str(value: float | int | None) -> str | None:
    """12 significant digits, round-half-even, as a decimal string for checksums."""
    if value is None:
        return None
    d = Decimal(str(float(value)))
    # Normalize to 12 significant digits
    normalized = f"{d:.{12}g}"
    # Re-parse and round-half-even at 12 sig digits via scientific form
    d2 = Decimal(normalized)
    # Emit without scientific notation when reasonable
    tup = d2.as_tuple()
    if tup.exponent is not None and isinstance(tup.exponent, int):
        q = d2.quantize(Decimal(1).scaleb(tup.exponent), rounding=ROUND_HALF_EVEN)
        s = format(q, "f")
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s or "0"
    return normalized


def _prepare_for_canonical(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return quantize_float_str(obj)
    if isinstance(obj, dict):
        return {str(k): _prepare_for_canonical(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_prepare_for_canonical(v) for v in obj]
    if hasattr(obj, "value"):  # Enum
        return str(obj.value)
    return str(obj)


def canonical_json_dumps(obj: Any) -> str:
    """Serialize with sorted keys and tight separators (canonical_json_hash_v1)."""
    prepared = _prepare_for_canonical(obj)
    return json.dumps(
        prepared, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def canonical_json_hash(obj: Any) -> str:
    """SHA-256 hex digest of canonical JSON UTF-8 bytes."""
    payload = canonical_json_dumps(obj).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
