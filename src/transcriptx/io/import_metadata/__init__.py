"""Import-metadata sidecar package: paths, schema, persistence, layout, validation."""

from transcriptx.io.import_metadata.layout import (  # noqa: F401
    ImportSidecarLayout,
    ImportSidecarResolution,
    resolve_import_sidecar_layout,
)
from transcriptx.io.import_metadata.paths import (  # noqa: F401
    find_existing_import_sidecar,
    legacy_flat_sidecar_path_for_transcript,
    mirrored_import_sidecar_path_for_transcript,
    sidecar_path_for_transcript,
)
from transcriptx.io.import_metadata.persist import (  # noqa: F401
    append_rename_history,
    compute_rename_history_payload,
    load_sidecar,
    write_initial_sidecar,
    write_json_atomic,
)
from transcriptx.io.import_metadata.schema import (  # noqa: F401
    SIDECAR_SCHEMA_VERSION,
    SIDECAR_SUFFIX,
    ImportMetadata,
    ManagedTranscriptCategory,
    ValidationResult,
    build_initial_sidecar,
)
from transcriptx.io.import_metadata.validate import (  # noqa: F401
    validate_managed_transcript,
)

__all__ = [
    "ImportSidecarLayout",
    "ImportSidecarResolution",
    "resolve_import_sidecar_layout",
    "SIDECAR_SCHEMA_VERSION",
    "SIDECAR_SUFFIX",
    "ImportMetadata",
    "ManagedTranscriptCategory",
    "ValidationResult",
    "append_rename_history",
    "build_initial_sidecar",
    "compute_rename_history_payload",
    "find_existing_import_sidecar",
    "legacy_flat_sidecar_path_for_transcript",
    "load_sidecar",
    "mirrored_import_sidecar_path_for_transcript",
    "sidecar_path_for_transcript",
    "validate_managed_transcript",
    "write_initial_sidecar",
    "write_json_atomic",
]
