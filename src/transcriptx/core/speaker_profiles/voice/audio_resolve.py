"""Managed-transcript-only audio resolution for voice matching.

Prohibits the analysis ``voice/audio_io.resolve_audio_path`` output_dir scan
fallback. Uses the authoritative managed association only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from transcriptx.core.speaker_profiles.voice.errors import VoiceFeatureError


class SourceAudioMissing(VoiceFeatureError):
    """No authoritative audio association for the managed transcript."""


class SourceAudioReplaced(VoiceFeatureError):
    """Audio identity changed mid-run (stat or content hash mismatch)."""


@dataclass(frozen=True)
class ManagedAudioIdentity:
    """Dual identity: cheap stat fingerprint + canonical content SHA-256."""

    audio_path: Path
    audio_stat_fingerprint: str
    audio_content_sha256: str


def compute_stat_fingerprint(path: Path) -> str:
    """Cheap identity: ``fastsha256:{size}:{mtime_ns}`` (plan dual-identity form)."""
    st = path.stat()
    mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))
    return f"fastsha256:{st.st_size}:{mtime_ns}"


def compute_content_sha256(path: Path) -> str:
    """Content hash with a path+stat cache to avoid rehashing unchanged audio."""
    from transcriptx.core.utils.run_manifest import compute_file_hash

    path = Path(path)
    stat_fp = compute_stat_fingerprint(path)
    cache_key = f"{path.resolve()}:{stat_fp}"
    cached = _CONTENT_HASH_CACHE.get(cache_key)
    if cached is not None:
        return cached
    digest = compute_file_hash(path, algorithm="sha256")
    if not digest:
        raise SourceAudioMissing(f"cannot hash audio: {path}")
    if not digest.startswith("sha256:"):
        digest = f"sha256:{digest}"
    # Bound cache size simply
    if len(_CONTENT_HASH_CACHE) > 256:
        _CONTENT_HASH_CACHE.clear()
    _CONTENT_HASH_CACHE[cache_key] = digest
    return digest


_CONTENT_HASH_CACHE: dict[str, str] = {}


def resolve_managed_transcript_audio(transcript_path: Path) -> ManagedAudioIdentity:
    """Resolve authoritative audio for a managed library transcript path.

    Uses ``find_original_audio_file`` only — never scans an output directory.
    """
    from transcriptx.core.utils.rename.audio_association import find_original_audio_file

    path = find_original_audio_file(str(transcript_path))
    if not path:
        raise SourceAudioMissing(
            f"no authoritative audio association for {transcript_path}"
        )
    audio = Path(path)
    if not audio.is_file():
        raise SourceAudioMissing(f"associated audio missing: {audio}")
    return ManagedAudioIdentity(
        audio_path=audio,
        audio_stat_fingerprint=compute_stat_fingerprint(audio),
        audio_content_sha256=compute_content_sha256(audio),
    )


def verify_audio_unchanged(identity: ManagedAudioIdentity) -> None:
    """Re-check stat + content after extraction; raise if replaced mid-run."""
    path = identity.audio_path
    if not path.is_file():
        raise SourceAudioReplaced(f"audio disappeared: {path}")
    if compute_stat_fingerprint(path) != identity.audio_stat_fingerprint:
        raise SourceAudioReplaced(f"audio stat fingerprint changed: {path}")
    if compute_content_sha256(path) != identity.audio_content_sha256:
        raise SourceAudioReplaced(f"audio content hash changed: {path}")
