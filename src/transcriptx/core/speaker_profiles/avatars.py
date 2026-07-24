"""Speaker profile avatar path rules, admission, and normalisation."""

from __future__ import annotations

import io
import re
from typing import Final

from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError
from transcriptx.core.speaker_profiles.hashing import sha256_bytes
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1

AVATAR_CONTENT_TYPE: Final = "image/webp"
AVATAR_FILENAME: Final = "avatar.webp"
MAX_UPLOAD_BYTES: Final = 2 * 1024 * 1024
MAX_DECODED_PIXELS: Final = 16_000_000
MAX_SIDE: Final = 4096
OUTPUT_SIDE: Final = 512
DATA_URL_MAX_BYTES: Final = 256 * 1024

_AVATAR_RELPATCH_RE = re.compile(
    r"^profiles/assets/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/avatar\.webp$"
)


def relative_avatar_path(profile_id: str) -> str:
    return f"profiles/assets/{profile_id}/{AVATAR_FILENAME}"


def validate_avatar_relpath(relpath: str, *, profile_id: str) -> str:
    if not isinstance(relpath, str) or not relpath:
        raise SpeakerProfileContractError("avatar_relpath must be a non-empty string")
    if (
        "\\" in relpath
        or relpath.startswith("/")
        or ".." in relpath.split("/")
        or relpath != relpath.strip()
    ):
        raise SpeakerProfileContractError("avatar_relpath path escape rejected")
    match = _AVATAR_RELPATCH_RE.fullmatch(relpath)
    if match is None:
        raise SpeakerProfileContractError(
            "avatar_relpath must be profiles/assets/{profile_id}/avatar.webp"
        )
    if match.group(1) != profile_id:
        raise SpeakerProfileContractError(
            "avatar_relpath profile_id does not match profile"
        )
    return relpath


def validate_avatar_field_set(
    *,
    avatar_relpath: str | None,
    avatar_sha256: str | None,
    avatar_content_type: str | None,
    profile_id: str,
) -> None:
    """All-null or all-set coherent trio."""
    values = (avatar_relpath, avatar_sha256, avatar_content_type)
    if all(v is None for v in values):
        return
    if any(v is None for v in values):
        raise SpeakerProfileContractError(
            "avatar_relpath, avatar_sha256, and avatar_content_type "
            "must all be null or all set"
        )
    assert avatar_relpath is not None
    assert avatar_sha256 is not None
    assert avatar_content_type is not None
    validate_avatar_relpath(avatar_relpath, profile_id=profile_id)
    if avatar_content_type != AVATAR_CONTENT_TYPE:
        raise SpeakerProfileContractError(
            f"avatar_content_type must be {AVATAR_CONTENT_TYPE!r}"
        )
    if not re.fullmatch(r"[0-9a-f]{64}", avatar_sha256):
        raise SpeakerProfileContractError("avatar_sha256 must be lowercase hex SHA-256")


def clear_avatar_fields(profile: SpeakerProfileV1) -> SpeakerProfileV1:
    return profile.model_copy(
        update={
            "avatar_relpath": None,
            "avatar_sha256": None,
            "avatar_content_type": None,
        }
    )


def set_avatar_fields(profile: SpeakerProfileV1, *, sha256: str) -> SpeakerProfileV1:
    relpath = relative_avatar_path(profile.profile_id)
    validate_avatar_field_set(
        avatar_relpath=relpath,
        avatar_sha256=sha256,
        avatar_content_type=AVATAR_CONTENT_TYPE,
        profile_id=profile.profile_id,
    )
    return profile.model_copy(
        update={
            "avatar_relpath": relpath,
            "avatar_sha256": sha256,
            "avatar_content_type": AVATAR_CONTENT_TYPE,
        }
    )


def normalize_avatar_image(raw: bytes) -> tuple[bytes, str]:
    """Admit upload bytes → normalised WebP + sha256.

    Raises SpeakerProfileContractError on admission failure.
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise SpeakerProfileContractError("avatar upload must be bytes")
    data = bytes(raw)
    if len(data) > MAX_UPLOAD_BYTES:
        raise SpeakerProfileContractError(
            f"avatar upload exceeds {MAX_UPLOAD_BYTES} bytes"
        )
    if len(data) == 0:
        raise SpeakerProfileContractError("avatar upload is empty")

    try:
        from PIL import Image, ImageOps, ImageSequence
    except ImportError as exc:
        raise SpeakerProfileContractError("Pillow required for avatar upload") from exc

    # Decompression bomb protection
    Image.MAX_IMAGE_PIXELS = MAX_DECODED_PIXELS
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise SpeakerProfileContractError(f"avatar image decode failed: {exc}") from exc

    fmt = (img.format or "").upper()
    if fmt not in {"JPEG", "JPG", "PNG", "WEBP"}:
        raise SpeakerProfileContractError(
            f"unsupported avatar format {fmt!r}; use JPEG, PNG, or WebP"
        )

    # Reject animated images (do not flatten silently)
    try:
        n_frames = getattr(img, "n_frames", 1) or 1
    except Exception:
        n_frames = 1
    if n_frames > 1:
        raise SpeakerProfileContractError("animated images are not allowed as avatars")
    # Extra animated WebP/PNG check via sequence
    frames = 0
    for _ in ImageSequence.Iterator(img):
        frames += 1
        if frames > 1:
            raise SpeakerProfileContractError(
                "animated images are not allowed as avatars"
            )
        break

    w, h = img.size
    if w <= 0 or h <= 0 or w > MAX_SIDE or h > MAX_SIDE or (w * h) > MAX_DECODED_PIXELS:
        raise SpeakerProfileContractError("avatar dimensions exceed limits")

    img = ImageOps.exif_transpose(img)

    # Colour mode + alpha onto white
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    else:
        img = img.convert("RGB")

    # Center-crop square then resize
    side = min(img.size)
    left = (img.width - side) // 2
    top = (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side))
    if img.width != OUTPUT_SIDE:
        img = img.resize((OUTPUT_SIDE, OUTPUT_SIDE), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    # Strip metadata by not copying info
    img.save(out, format="WEBP", quality=90, method=6)
    webp = out.getvalue()
    digest = sha256_bytes(webp)
    return webp, digest


def verify_avatar_bytes(data: bytes, *, expected_sha256: str) -> bool:
    return sha256_bytes(data) == expected_sha256
