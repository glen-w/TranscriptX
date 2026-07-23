"""Defined ``.npy`` vector format for voice embeddings (dtype <f4)."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import numpy as np

from transcriptx.core.speaker_profiles.voice.errors import VoiceFeatureError

VECTOR_DTYPE = np.dtype("<f4")
L2_NORM_EPSILON = 1e-3
EXPECTED_DIM = 192


class VoiceVectorError(VoiceFeatureError):
    """Invalid embedding vector file or array."""


def l2_normalize(vector: np.ndarray, *, eps: float = 1e-12) -> np.ndarray:
    arr = np.asarray(vector, dtype=VECTOR_DTYPE)
    if arr.ndim != 1:
        raise VoiceVectorError(f"expected 1-D vector, got shape {arr.shape}")
    if not np.isfinite(arr).all():
        raise VoiceVectorError("non-finite values in embedding")
    norm = float(np.linalg.norm(arr))
    if norm < eps:
        raise VoiceVectorError("embedding L2 norm too small")
    out = (arr / norm).astype(VECTOR_DTYPE, copy=False)
    return out


def validate_embedding_vector(
    vector: np.ndarray,
    *,
    expected_dim: int = EXPECTED_DIM,
    require_unit_norm: bool = True,
) -> np.ndarray:
    arr = np.asarray(vector)
    if arr.dtype != VECTOR_DTYPE:
        arr = arr.astype(VECTOR_DTYPE, copy=False)
    if arr.shape != (expected_dim,):
        raise VoiceVectorError(
            f"expected shape ({expected_dim},), got {arr.shape}"
        )
    if not np.isfinite(arr).all():
        raise VoiceVectorError("non-finite values in embedding")
    if require_unit_norm:
        norm = float(np.linalg.norm(arr))
        if abs(norm - 1.0) > L2_NORM_EPSILON:
            raise VoiceVectorError(
                f"L2 norm {norm} outside unit band ±{L2_NORM_EPSILON}"
            )
    return arr


def vector_sha256(vector: np.ndarray) -> str:
    arr = validate_embedding_vector(vector, require_unit_norm=False)
    digest = hashlib.sha256(arr.tobytes(order="C")).hexdigest()
    return f"sha256:{digest}"


def write_vector_npy(path: Path, vector: np.ndarray) -> dict[str, object]:
    """Atomic write of little-endian float32 ``.npy``; returns metadata fields."""
    data, meta = encode_vector_npy_bytes(vector)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        suffix=".npy", dir=str(path.parent), prefix=".tmp_vec_"
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_bytes(data)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    return meta


def encode_vector_npy_bytes(vector: np.ndarray) -> tuple[bytes, dict[str, object]]:
    """Encode vector to ``.npy`` bytes in memory (no live-tree write)."""
    import io

    arr = l2_normalize(vector)
    arr = validate_embedding_vector(arr)
    buf = io.BytesIO()
    np.save(buf, arr, allow_pickle=False)
    data = buf.getvalue()
    meta = {
        "vector_sha256": vector_sha256(arr),
        "nbytes": len(arr.tobytes(order="C")),
        "dimension": int(arr.shape[0]),
        "dtype": "<f4",
        "file_sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
    }
    return data, meta


def load_vector_npy(
    path: Path,
    *,
    expected_sha256: str | None = None,
    expected_dim: int = EXPECTED_DIM,
) -> np.ndarray:
    """Load with ``allow_pickle=False``; reject wrong shape/dtype/norm/hash."""
    path = Path(path)
    raw = path.read_bytes()
    # Detect trailing data: numpy load from BytesIO and compare consumed length
    import io

    bio = io.BytesIO(raw)
    arr = np.load(bio, allow_pickle=False)
    if bio.tell() != len(raw):
        raise VoiceVectorError("trailing data after .npy payload")
    if not isinstance(arr, np.ndarray):
        raise VoiceVectorError("unexpected .npy object type")
    if arr.dtype != VECTOR_DTYPE:
        # Accept native f4 only if byte-identical endianness on LE hosts after cast check
        if arr.dtype.str not in ("<f4", "|f4", "=f4") and arr.dtype != np.float32:
            raise VoiceVectorError(f"dtype must be <f4, got {arr.dtype}")
        arr = arr.astype(VECTOR_DTYPE, copy=False)
    arr = validate_embedding_vector(arr, expected_dim=expected_dim)
    digest = vector_sha256(arr)
    if expected_sha256 is not None and digest != expected_sha256:
        raise VoiceVectorError("vector SHA-256 mismatch")
    return arr
