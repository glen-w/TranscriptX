"""
Centralized path and file naming utilities for TranscriptX.

This module provides a single source of truth for all file path generation
and naming conventions used throughout the TranscriptX codebase. It eliminates
the duplication of path generation logic that was previously scattered across
all analysis modules.

Key Features:
- Consistent file naming conventions
- Centralized path generation logic
- Automatic directory creation
- Validation of path structures
- Support for all analysis module output patterns

Usage:
    from transcriptx.core.utils.path_utils import get_base_name, get_transcript_dir

    base_name = get_base_name("/path/to/transcript.json")
    transcript_dir = get_transcript_dir("/path/to/transcript.json")

Note: This module is a public API that re-exports functions from internal
modules (_path_core, _path_resolution, _path_cache). The internal structure
may change, but the public API remains stable.
"""

# Re-export all public functions from internal modules
# This maintains 100% backward compatibility with existing code

# Core path utilities
from transcriptx.core.utils._path_core import (
    get_canonical_base_name,
    get_base_name,
    get_transcript_dir,
    get_group_output_dir,
    get_module_output_dir,
    get_module_data_file,
    get_enriched_transcript_path,
    get_enriched_transcript_path_legacy,
    find_enriched_transcript,
    ensure_output_dirs,
    get_stats_summary_path,
    get_html_summary_path,
    validate_transcript_path,
    get_relative_output_path,
    set_transcript_output_dir,
    clear_transcript_output_dir,
)

# Path resolution
from transcriptx.core.utils._path_resolution import (
    resolve_file_path,
)

# Cache management
from transcriptx.core.utils._path_cache import (
    get_cache_stats,
    invalidate_path_cache,
)

# Make all functions available at module level
__all__ = [
    # Core path utilities
    "get_canonical_base_name",
    "get_base_name",
    "get_transcript_dir",
    "get_group_output_dir",
    "get_module_output_dir",
    "get_module_data_file",
    "get_enriched_transcript_path",
    "get_enriched_transcript_path_legacy",
    "find_enriched_transcript",
    "ensure_output_dirs",
    "get_stats_summary_path",
    "get_html_summary_path",
    "validate_transcript_path",
    "get_relative_output_path",
    "set_transcript_output_dir",
    "clear_transcript_output_dir",
    # Path resolution
    "resolve_file_path",
    # Cache management
    "get_cache_stats",
    "invalidate_path_cache",
]
