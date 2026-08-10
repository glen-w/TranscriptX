"""ClipTransport T0 — measured base64 inside JSON workspace data."""

from __future__ import annotations

import base64


def encode_clip_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def decode_clip_b64(payload: str) -> bytes:
    return base64.b64decode(payload.encode("ascii"), validate=True)


def within_clip_budget(nbytes: int, max_bytes: int) -> bool:
    return 0 <= nbytes <= max_bytes
