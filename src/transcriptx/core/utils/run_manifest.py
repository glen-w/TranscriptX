"""
Run manifest system for reproducibility.

This module provides functionality to create and manage run manifests,
which record all information needed to reproduce an analysis run.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.artifact_writer import write_json
from transcriptx.core.utils.paths import OUTPUTS_DIR

logger = get_logger()


@dataclass
class RunManifest:
    """
    Run manifest containing provenance and reproducibility metadata.
    """

    schema_version: str
    transcript_hash: str
    canonical_schema_version: str
    config_hash: Optional[str]
    code_version: str
    module_versions: Dict[str, str]
    artifact_index: List[Dict[str, Any]]
    timestamp: str
    transcript_file_hash: Optional[str] = None
    transcript_identity_hash: Optional[str] = None
    transcript_content_hash_full: Optional[str] = None
    config_effective_path: Optional[str] = None
    config_override_path: Optional[str] = None
    config_schema_version: Optional[int] = None
    config_source: Optional[str] = None
    transcript_path: Optional[str] = None
    source_basename: Optional[str] = None
    source_path: Optional[str] = None
    run_id: Optional[str] = None
    config_snapshot_hash: Optional[str] = None
    config_snapshot: Optional[Dict[str, Any]] = None
    module_metadata: Optional[Dict[str, Any]] = None
    artifacts: Optional[List[Dict[str, Any]]] = None
    execution_order: Optional[List[str]] = None
    modules_run: Optional[List[str]] = None
    errors: Optional[List[str]] = None
    output_dir: Optional[str] = None
    rerun_mode: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert manifest to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunManifest":
        """Create manifest from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "RunManifest":
        """Create manifest from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> Optional[str]:
    """
    Compute hash of a file.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm to use (default: sha256)

    Returns:
        Hex digest of file hash, or None if file doesn't exist
    """
    if not file_path.exists():
        return None

    try:
        hash_obj = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        return f"{algorithm}:{hash_obj.hexdigest()}"
    except Exception as e:
        logger.warning(f"Failed to compute hash for {file_path}: {e}")
        return None


def get_dependency_versions() -> Dict[str, str]:
    """
    Get versions of key dependencies.

    Returns:
        Dictionary mapping package names to versions
    """
    versions = {}

    # Core dependencies
    packages = [
        "numpy",
        "pandas",
        "scikit-learn",
        "nltk",
        "spacy",
        "transformers",
        "torch",
        "plotly",
        "matplotlib",
    ]

    for package in packages:
        try:
            mod = __import__(package)
            if hasattr(mod, "__version__"):
                versions[package] = mod.__version__
        except ImportError:
            pass

    return versions


def get_transcriptx_version() -> str:
    """Get TranscriptX version."""
    try:
        from transcriptx import __version__

        return __version__
    except ImportError:
        return "unknown"


def create_run_manifest(
    transcript_hash: Optional[str] = None,
    canonical_schema_version: str = "1.0",
    selected_modules: Optional[List[str]] = None,
    artifact_index: Optional[List[Dict[str, Any]]] = None,
    transcript_file_hash: Optional[str] = None,
    transcript_identity_hash: Optional[str] = None,
    transcript_content_hash_full: Optional[str] = None,
    config_hash: Optional[str] = None,
    config_effective_path: Optional[str] = None,
    config_override_path: Optional[str] = None,
    config_schema_version: Optional[int] = None,
    config_source: Optional[str] = None,
    transcript_path: Optional[str] = None,
    source_basename: Optional[str] = None,
    source_path: Optional[str] = None,
    run_id: Optional[str] = None,
    execution_order: Optional[List[str]] = None,
    modules_run: Optional[List[str]] = None,
    errors: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
    rerun_mode: Optional[str] = None,
) -> RunManifest:
    """
    Create a run manifest for an analysis run.

    Args:
        transcript_hash: Legacy transcript hash (kept for backward compatibility)
        transcript_file_hash: Hash of the transcript file bytes (preferred for verification)
        transcript_identity_hash: Stable hash based on text + timestamps
        transcript_content_hash_full: Full segments hash for traceability
        canonical_schema_version: Version of canonical schema
        selected_modules: List of selected analysis modules
        artifact_index: List of artifacts generated
        transcript_path: Path to transcript file (optional)
        source_basename: Source basename (optional, extracted from transcript_path if not provided)
        source_path: Source path (optional, defaults to transcript_path)
        run_id: Run ID for this analysis run (optional)

    Returns:
        RunManifest object
    """
    selected_modules = selected_modules or []
    artifact_index = artifact_index or []

    if transcript_hash is None and transcript_path:
        transcript_hash = compute_file_hash(Path(transcript_path)) or "sha256:unknown"
    elif transcript_hash is None:
        transcript_hash = "sha256:unknown"

    # Compute config hash if not provided
    config_snapshot: Optional[Dict[str, Any]] = None
    if config_hash is None:
        try:
            config = get_config()
            config_snapshot = config.to_dict() if hasattr(config, "to_dict") else None
            if config_snapshot is not None:
                serialized = json.dumps(
                    config_snapshot,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
                config_hash = (
                    f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"
                )
        except Exception as e:
            logger.warning(f"Failed to compute config hash: {e}")

    module_versions: Dict[str, str] = {}
    try:
        from transcriptx.core.utils.module_hashing import compute_module_source_hash

        for module in selected_modules:
            module_versions[module] = compute_module_source_hash(module)
    except Exception as e:
        logger.warning(f"Failed to compute module versions: {e}")

    # Extract source_basename if not provided
    if source_basename is None and transcript_path:
        from transcriptx.core.utils._path_core import get_canonical_base_name

        source_basename = get_canonical_base_name(transcript_path)

    # Use transcript_path as source_path if not provided
    if source_path is None:
        source_path = transcript_path

    manifest = RunManifest(
        schema_version="1.0",
        transcript_hash=transcript_hash,
        transcript_file_hash=transcript_file_hash,
        transcript_identity_hash=transcript_identity_hash,
        transcript_content_hash_full=transcript_content_hash_full,
        canonical_schema_version=canonical_schema_version,
        config_hash=config_hash,
        code_version=get_transcriptx_version(),
        module_versions=module_versions,
        artifact_index=artifact_index,
        timestamp=datetime.utcnow().isoformat() + "Z",
        config_effective_path=config_effective_path,
        config_override_path=config_override_path,
        config_schema_version=config_schema_version,
        config_source=config_source,
        transcript_path=transcript_path,
        source_basename=source_basename,
        source_path=source_path,
        run_id=run_id,
        config_snapshot_hash=config_hash,
        config_snapshot=config_snapshot,
        module_metadata=module_versions,
        artifacts=artifact_index,
        execution_order=execution_order,
        modules_run=modules_run,
        errors=errors,
        output_dir=output_dir,
        rerun_mode=rerun_mode,
    )

    return manifest


def save_run_manifest(manifest: RunManifest, output_dir: Optional[str] = None) -> Path:
    """
    Save run manifest to disk.

    Args:
        manifest: RunManifest to save
        output_dir: Output directory (default: uses manifest.output_dir or transcript dir)

    Returns:
        Path to saved manifest file
    """
    if output_dir is None:
        output_dir = str(Path(OUTPUTS_DIR))

    # Create .transcriptx subdirectory
    manifest_dir = Path(output_dir) / ".transcriptx"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    # Save manifest
    manifest_path = manifest_dir / "manifest.json"
    write_json(manifest_path, manifest.to_dict(), indent=2, ensure_ascii=False)

    logger.info(f"Saved run manifest to {manifest_path}")
    return manifest_path


def load_run_manifest(manifest_path: Path) -> RunManifest:
    """
    Load run manifest from disk.

    Args:
        manifest_path: Path to manifest file

    Returns:
        RunManifest object
    """
    with open(manifest_path, "r") as f:
        data = json.load(f)
    return RunManifest.from_dict(data)


def verify_run_manifest(manifest: RunManifest) -> Dict[str, Any]:
    """
    Verify that a run manifest can be used to reproduce a run.

    Checks:
    - Transcript file exists and hash matches
    - Speaker map file exists and hash matches (if specified)
    - Configuration is compatible

    Args:
        manifest: RunManifest to verify

    Returns:
        Dictionary with verification results
    """
    results = {"valid": True, "errors": [], "warnings": []}

    # Check transcript file if path is available
    if manifest.transcript_path:
        transcript_path = Path(manifest.transcript_path)
        if not transcript_path.exists():
            results["valid"] = False
            results["errors"].append(
                f"Transcript file not found: {manifest.transcript_path}"
            )
        else:
            current_hash = compute_file_hash(transcript_path)
            expected_hash = manifest.transcript_file_hash or manifest.transcript_hash
            if expected_hash and current_hash != expected_hash:
                results["valid"] = False
                results["errors"].append(
                    "Transcript file hash mismatch - file may have been modified"
                )
            elif expected_hash is None:
                results["warnings"].append(
                    "No transcript file hash recorded in manifest"
                )

    return results
