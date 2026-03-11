"""
Audio fingerprinting utilities for content-based duplicate detection.

This module provides functions for generating audio fingerprints and comparing
audio files to detect duplicates based on actual audio content, not just file size.
Uses librosa for robust audio feature extraction.
"""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    import librosa

    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    librosa = None

from transcriptx.core.utils.logger import get_logger, log_error

logger = get_logger()

# Cache for audio fingerprints to avoid recomputing
_fingerprint_cache: Dict[Path, Optional[np.ndarray]] = {}


def compute_audio_fingerprint(
    file_path: Path, use_cache: bool = True
) -> Optional[np.ndarray]:
    """
    Generate an audio fingerprint for a file using librosa's chroma features.

    The fingerprint is a compact representation of the audio content that can be
    used to compare files for similarity. Uses chroma features which are
    robust to pitch shifts and tempo variations.

    Args:
        file_path: Path to audio file
        use_cache: Whether to use cached fingerprint if available (default: True)

    Returns:
        numpy array representing the audio fingerprint, or None if computation fails

    Note:
        - Normalizes audio to mono and 22050 Hz sample rate
        - Uses chroma_cqt for robust feature extraction
        - Returns mean chroma features as a compact fingerprint
    """
    if not LIBROSA_AVAILABLE:
        logger.warning(
            "librosa is not available. Install with: pip install librosa>=0.10.0"
        )
        return None

    # Check cache first
    if use_cache and file_path in _fingerprint_cache:
        return _fingerprint_cache[file_path]

    try:
        # Load audio file, normalize to mono and 22050 Hz
        # This ensures consistent comparison regardless of original format
        y, sr = librosa.load(
            str(file_path),
            sr=22050,  # Standard sample rate for fingerprinting
            mono=True,  # Convert to mono for comparison
            duration=None,  # Load entire file
            res_type="kaiser_best",  # High quality resampling
        )

        # Check if audio is too short (less than 0.1 seconds)
        if len(y) < sr * 0.1:
            logger.warning(
                f"Audio file {file_path.name} is too short for fingerprinting"
            )
            _fingerprint_cache[file_path] = None
            return None

        # Compute chroma features using Constant-Q Transform
        # Chroma features are pitch-class profiles that are robust to timbre variations
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

        # Compute mean chroma across time to get a compact fingerprint
        # This gives us a 12-dimensional vector (one per semitone)
        fingerprint = np.mean(chroma, axis=1)

        # Cache the result
        if use_cache:
            _fingerprint_cache[file_path] = fingerprint

        return fingerprint

    except Exception as e:
        log_error(
            "AUDIO_FINGERPRINTING",
            f"Failed to compute fingerprint for {file_path}: {e}",
            exception=e,
        )
        # Cache None to avoid repeated failed attempts
        if use_cache:
            _fingerprint_cache[file_path] = None
        return None


def compare_audio_files(
    file1: Path, file2: Path, threshold: float = 0.90, use_cache: bool = True
) -> Tuple[bool, float]:
    """
    Compare two audio files and determine if they are duplicates.

    Args:
        file1: Path to first audio file
        file2: Path to second audio file
        threshold: Similarity threshold (0.0 to 1.0). Files with similarity >= threshold
                   are considered duplicates. Default: 0.90 (90%)
        use_cache: Whether to use cached fingerprints (default: True)

    Returns:
        Tuple of (is_duplicate: bool, similarity_score: float)
        - is_duplicate: True if similarity >= threshold
        - similarity_score: Cosine similarity between fingerprints (0.0 to 1.0)

    Note:
        - Returns (False, 0.0) if fingerprinting fails for either file
        - Uses cosine similarity for comparison
    """
    if not LIBROSA_AVAILABLE:
        logger.warning("librosa is not available for audio comparison")
        return False, 0.0

    # Compute fingerprints for both files
    fp1 = compute_audio_fingerprint(file1, use_cache=use_cache)
    fp2 = compute_audio_fingerprint(file2, use_cache=use_cache)

    # If either fingerprint failed, cannot compare
    if fp1 is None or fp2 is None:
        return False, 0.0

    # Compute cosine similarity
    # Normalize fingerprints to unit vectors
    norm1 = np.linalg.norm(fp1)
    norm2 = np.linalg.norm(fp2)

    if norm1 == 0 or norm2 == 0:
        # One of the fingerprints is all zeros (silence)
        return False, 0.0

    # Cosine similarity: dot product of normalized vectors
    similarity = np.dot(fp1 / norm1, fp2 / norm2)

    # Clamp similarity to [0, 1] range (should already be in range, but safety check)
    similarity = max(0.0, min(1.0, similarity))

    is_duplicate = similarity >= threshold

    return is_duplicate, float(similarity)


def batch_compare_audio_group(
    files: List[Path], threshold: float = 0.90, use_cache: bool = True
) -> Dict[Path, List[Path]]:
    """
    Compare all files in a group and return duplicate groups.

    This function performs pairwise comparison of all files and groups them
    into duplicate clusters. Files are considered duplicates if they have
    similarity >= threshold with at least one other file in the group.

    Args:
        files: List of file paths to compare
        threshold: Similarity threshold for duplicate detection (default: 0.90)
        use_cache: Whether to use cached fingerprints (default: True)

    Returns:
        Dictionary mapping each file path to a list of its duplicate file paths.
        Only includes files that have at least one duplicate.

    Note:
        - Uses transitive closure: if A matches B and B matches C, then A, B, C are all grouped
        - Files that don't match any others are not included in the result
    """
    if not LIBROSA_AVAILABLE:
        logger.warning("librosa is not available for batch audio comparison")
        return {}

    if len(files) < 2:
        return {}

    # Build similarity matrix
    similarity_matrix: Dict[Tuple[Path, Path], float] = {}
    duplicate_pairs: List[Tuple[Path, Path]] = []

    # Compare all pairs
    for i, file1 in enumerate(files):
        for file2 in files[i + 1 :]:
            is_dup, similarity = compare_audio_files(
                file1, file2, threshold=threshold, use_cache=use_cache
            )
            similarity_matrix[(file1, file2)] = similarity

            if is_dup:
                duplicate_pairs.append((file1, file2))

    # Build duplicate groups using union-find approach
    # Each file maps to its "representative" (root of its group)
    parent: Dict[Path, Path] = {f: f for f in files}

    def find_root(file: Path) -> Path:
        """Find the root representative of a file's group."""
        if parent[file] != file:
            parent[file] = find_root(parent[file])  # Path compression
        return parent[file]

    def union(file1: Path, file2: Path):
        """Merge two files into the same group."""
        root1 = find_root(file1)
        root2 = find_root(file2)
        if root1 != root2:
            parent[root2] = root1

    # Union all duplicate pairs
    for file1, file2 in duplicate_pairs:
        union(file1, file2)

    # Build result: group files by their root representative
    groups: Dict[Path, List[Path]] = {}
    for file in files:
        root = find_root(file)
        if root not in groups:
            groups[root] = []
        groups[root].append(file)

    # Only return groups with 2+ files (actual duplicates)
    duplicate_groups: Dict[Path, List[Path]] = {}
    for root, group_files in groups.items():
        if len(group_files) > 1:
            # Use the first file as the key (arbitrary but consistent)
            duplicate_groups[group_files[0]] = group_files

    return duplicate_groups


def clear_fingerprint_cache():
    """Clear the fingerprint cache. Useful for freeing memory."""
    global _fingerprint_cache
    _fingerprint_cache.clear()


def is_librosa_available() -> bool:
    """
    Check if librosa is available for audio fingerprinting.

    This function dynamically checks for librosa availability at runtime,
    not just at module import time. This allows detection of librosa even
    if it was installed after the module was first imported.
    """
    global LIBROSA_AVAILABLE, librosa

    # Respect explicit overrides
    if LIBROSA_AVAILABLE is False:
        return False
    if LIBROSA_AVAILABLE:
        return True

    # Try to import librosa to check if it's now available
    try:
        import librosa as _librosa

        # Update module-level variables
        librosa = _librosa
        LIBROSA_AVAILABLE = True
        return True
    except ImportError:
        LIBROSA_AVAILABLE = False
        librosa = None
        return False


def canonicalize_fingerprint(fingerprint: np.ndarray) -> bytes:
    """
    Canonicalize fingerprint vector for consistent hashing.

    Ensures same audio content always produces same hash across runs.

    Rules:
    1. Convert to float32 (4 bytes per float)
    2. Round to 6 decimal places
    3. Pack as little-endian bytes

    Args:
        fingerprint: 12-dimensional numpy array

    Returns:
        Canonicalized bytes representation
    """
    # Convert to float32
    fp_float32 = fingerprint.astype(np.float32)
    # Round to 6 decimal places
    fp_rounded = np.round(fp_float32, decimals=6)
    # Pack as little-endian bytes
    return fp_rounded.tobytes()


def compute_fingerprint_hash(fingerprint: np.ndarray, version: int = 1) -> str:
    """
    Compute SHA256 hash of canonicalized fingerprint.

    Args:
        fingerprint: 12-dimensional numpy array
        version: Fingerprint version (default: 1)

    Returns:
        SHA256 hash as hex string (64 characters)
    """
    canonical = canonicalize_fingerprint(fingerprint)
    hash_obj = hashlib.sha256(canonical)
    return hash_obj.hexdigest()


def get_or_create_file_entity(
    fingerprint_hash: str,
    fingerprint_vector: np.ndarray,
    file_path: Path,
    duration_seconds: Optional[float] = None,
    fingerprint_version: int = 1,
):
    """
    Get existing or create new file entity in database.

    ENFORCES: Single entity per fingerprint hash.
    Returns existing entity if fingerprint_hash exists.

    Args:
        fingerprint_hash: SHA256 hash of canonicalized fingerprint
        fingerprint_vector: 12-dimensional fingerprint array
        file_path: Path to the file (for metadata)
        duration_seconds: Audio duration in seconds
        fingerprint_version: Version of fingerprint algorithm (default: 1)

    Returns:
        FileEntity instance (existing or newly created)
    """
    from transcriptx.database import get_session, FileTrackingService

    session = get_session()
    tracking_service = FileTrackingService(session)

    try:
        # Convert numpy array to list for JSON storage
        fingerprint_list = fingerprint_vector.tolist()

        entity = tracking_service.get_or_create_file_entity(
            fingerprint_hash=fingerprint_hash,
            fingerprint_vector=fingerprint_list,
            fingerprint_version=fingerprint_version,
            duration_seconds=duration_seconds,
            metadata={"source_path": str(file_path)},
        )

        session.commit()
        return entity
    except Exception as e:
        session.rollback()
        log_error(
            "FILE_TRACKING", f"Failed to get or create file entity: {e}", exception=e
        )
        raise
