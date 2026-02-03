"""
Output validation utilities for TranscriptX.

This module provides functionality to validate that all expected analysis modules
have generated proper outputs.
"""

from dataclasses import dataclass
from pathlib import Path


def _get_module_output_dir(basename_dir: Path, module_name: str) -> Path:
    """
    Resolve the actual output directory for a module (must match output_reporter).

    - Modules with output_namespace/output_version (e.g. voice_charts_core) use
      basename_dir / namespace / version.
    - transcript_output writes to run root (transcripts/ subdir); use basename_dir.
    - simplified_transcript writes to basename_dir/transcripts/; use that.
    - Others use basename_dir / module_name.
    """
    if module_name == "transcript_output":
        return basename_dir
    if module_name == "simplified_transcript":
        return basename_dir / "transcripts"
    try:
        from transcriptx.core.pipeline.module_registry import get_module_info
        info = get_module_info(module_name)
        if info and getattr(info, "output_namespace", None) and getattr(info, "output_version", None):
            return basename_dir / info.output_namespace / info.output_version
    except Exception:
        pass
    return basename_dir / module_name


@dataclass
class ModuleValidationRule:
    """Validation rule for a specific module's outputs."""

    required_files: list[str]  # File patterns to check for
    required_dirs: list[str]  # Directories that must exist
    min_files: int = 0  # Minimum number of files expected
    file_extensions: set[str] = None  # Expected file extensions


# Define validation rules for each module
MODULE_VALIDATION_RULES = {
    "wordclouds": ModuleValidationRule(
        required_files=["*.png"],
        required_dirs=["charts/global", "charts/speakers"],
        min_files=5,  # At least 5 PNG files expected
        file_extensions={".png"},
    ),
    "sentiment": ModuleValidationRule(
        required_files=["*_with_sentiment.json"],  # Actual file pattern used
        required_dirs=["data"],  # Just check for data directory
        min_files=1,  # At least 1 main data file
        file_extensions={".json", ".csv"},
    ),
    "emotion": ModuleValidationRule(
        required_files=["*_with_emotion.json"],  # Actual file pattern used
        required_dirs=["data"],  # Just check for data directory
        min_files=1,  # At least 1 main data file
        file_extensions={".json", ".csv"},
    ),
    "acts": ModuleValidationRule(
        required_files=["*_with_acts.json"],  # Main output file always created
        required_dirs=["data"],  # Check for data directory (always created)
        min_files=1,  # At least 1 main data file
        file_extensions={".json", ".csv", ".txt"},
    ),
    "interactions": ModuleValidationRule(
        required_files=["*_interactions_summary.json"],  # Actual file pattern used
        required_dirs=[
            "data/global",
            "charts/global",
        ],  # Check for both data and charts
        min_files=2,  # At least summary + chart
        file_extensions={".json", ".png"},
    ),
    "ner": ModuleValidationRule(
        required_files=[
            "*_ner-entities.json"
        ],  # Updated to use underscore for consistency
        required_dirs=["data"],  # Just check for data directory
        min_files=1,  # At least 1 main data file
        file_extensions={".json", ".csv", ".txt"},
    ),
    "entity_sentiment": ModuleValidationRule(
        required_files=["*_entity_sentiment.json"],  # Actual file pattern used
        required_dirs=["data"],  # Just check for data directory
        min_files=1,  # At least 1 main data file
        file_extensions={".json", ".csv"},
    ),
    "conversation_loops": ModuleValidationRule(
        required_files=["*_conversation_loops.json"],  # Actual file pattern used
        required_dirs=["data"],  # Just check for data directory
        min_files=1,  # At least 1 main data file
        file_extensions={".json", ".csv"},
    ),
    "contagion": ModuleValidationRule(
        required_files=["*_contagion_summary.json"],  # Actual file pattern used
        required_dirs=["data"],  # Just check for data directory
        min_files=1,  # At least 1 main data file
        file_extensions={".json", ".csv"},
    ),
    "topic_modeling": ModuleValidationRule(
        required_files=["*_enhanced_lda_topics.json"],  # Actual file pattern used
        required_dirs=["data"],  # Just check for data directory
        min_files=1,  # At least 1 main data file
        file_extensions={".json", ".csv", ".png", ".html"},
    ),
    "semantic_similarity": ModuleValidationRule(
        required_files=[
            "*_semantic_similarity_summary.json"
        ],  # Actual file pattern used
        required_dirs=[
            "data/global",
            "charts/global",
        ],  # Check for both data and charts
        min_files=2,  # At least summary + chart
        file_extensions={".json", ".png"},
    ),
    "stats": ModuleValidationRule(
        required_files=["*_comprehensive_summary.txt"],  # Actual file pattern used
        required_dirs=[],  # No specific directory requirement
        min_files=1,  # At least 1 summary file
        file_extensions={".txt", ".html"},
    ),
    "transcript_output": ModuleValidationRule(
        required_files=["transcripts/*.txt", "transcripts/*.csv"],
        required_dirs=["transcripts"],
        min_files=1,  # At least one transcript file (txt or csv)
        file_extensions={".txt", ".csv"},
    ),
    "simplified_transcript": ModuleValidationRule(
        required_files=["*_simplified_transcript.json", "*_simplified_transcript_summary.json"],
        required_dirs=[],  # writes under transcripts/, no data/ subdir
        min_files=1,
        file_extensions={".json"},
    ),
    "tics": ModuleValidationRule(
        required_files=["*_tics_summary.json"],  # Actual file pattern used
        required_dirs=["data"],  # Just check for data directory
        min_files=1,  # At least 1 main data file
        file_extensions={".json", ".csv", ".txt"},
    ),
    "understandability": ModuleValidationRule(
        required_files=[
            "*_understandability.json"
        ],  # Updated to use underscore for consistency
        required_dirs=["data"],  # Just check for data directory
        min_files=1,  # At least 1 main data file
        file_extensions={".json", ".csv"},
    ),
    "semantic_similarity_advanced": ModuleValidationRule(
        required_files=["*_semantic_advanced_global.json"],  # Actual file pattern used
        required_dirs=["data"],  # Just check for data directory
        min_files=1,  # At least 1 main data file
        file_extensions={".json", ".png"},
    ),
}


def check_module_has_outputs(
    module_dir: Path, module_name: str
) -> tuple[bool, list[str]]:
    """
    Check if a specific module has generated valid outputs.
    Now returns warnings instead of failures to be more lenient.

    Args:
        module_dir: Path to the module's output directory
        module_name: Name of the module to validate

    Returns:
        Tuple of (is_valid, list_of_warnings)
    """
    if not module_dir.exists():
        return False, [f"Module directory does not exist: {module_dir}"]

    if module_name not in MODULE_VALIDATION_RULES:
        # If no specific rules, just check that directory exists and has some files
        files = list(module_dir.rglob("*"))
        if not files:
            return False, [f"Module directory is empty: {module_dir}"]
        return True, []

    rule = MODULE_VALIDATION_RULES[module_name]
    warnings = []

    # Check required directories
    for required_dir in rule.required_dirs:
        dir_path = module_dir / required_dir
        if not dir_path.exists():
            warnings.append(f"Required directory missing: {required_dir}")

    # Check required files and count total valid files
    total_files = 0
    required_files_found = 0

    # First, check for required file patterns
    for pattern in rule.required_files:
        files = list(module_dir.rglob(pattern))
        if not files:
            warnings.append(f"No files matching pattern: {pattern}")
        else:
            required_files_found += len(files)

    # Count all valid files (matching expected extensions)
    if rule.file_extensions:
        all_files = list(module_dir.rglob("*"))
        valid_files = [
            f for f in all_files if f.is_file() and f.suffix in rule.file_extensions
        ]
        total_files = len(valid_files)

        if not valid_files:
            warnings.append(
                f"No files with expected extensions: {rule.file_extensions}"
            )
    else:
        # If no specific extensions required, count all files
        all_files = list(module_dir.rglob("*"))
        total_files = len([f for f in all_files if f.is_file()])

    # Check minimum file count - use total valid files, not just required patterns
    if total_files < rule.min_files:
        warnings.append(
            f"Insufficient files: found {total_files}, expected at least {rule.min_files}"
        )

    # Always return True now (warnings instead of failures)
    return True, warnings


def validate_module_outputs(
    basename_dir: Path, expected_modules: list[str]
) -> dict[str, tuple[bool, list[str]]]:
    """
    Validate that all expected modules have generated outputs.
    Now returns warnings instead of failures to be more lenient.

    Args:
        basename_dir: Base directory containing all module outputs
        expected_modules: List of modules to validate

    Returns:
        Dict mapping module_name -> (is_valid, list_of_warnings)
    """
    results = {}

    for module_name in expected_modules:
        module_dir = _get_module_output_dir(basename_dir, module_name)
        is_valid, warnings = check_module_has_outputs(module_dir, module_name)
        results[module_name] = (is_valid, warnings)

    return results


def get_modules_with_warnings(
    basename_dir: Path, expected_modules: list[str]
) -> list[str]:
    """
    Get list of modules that have validation warnings.

    Args:
        basename_dir: Base directory containing all module outputs
        expected_modules: List of modules to check

    Returns:
        List of module names that have warnings
    """
    validation_results = validate_module_outputs(basename_dir, expected_modules)
    return [module for module, (_, warnings) in validation_results.items() if warnings]


def get_validation_summary(
    basename_dir: Path, expected_modules: list[str]
) -> dict[str, any]:
    """
    Get a comprehensive validation summary with warnings.

    Args:
        basename_dir: Base directory containing all module outputs
        expected_modules: List of modules to validate

    Returns:
        Dictionary with validation summary
    """
    validation_results = validate_module_outputs(basename_dir, expected_modules)

    modules_with_warnings = []
    modules_without_warnings = []
    total_warnings = 0

    for module_name, (is_valid, warnings) in validation_results.items():
        if warnings:
            modules_with_warnings.append(module_name)
            total_warnings += len(warnings)
        else:
            modules_without_warnings.append(module_name)

    return {
        "total_modules": len(validation_results),
        "modules_without_warnings": modules_without_warnings,
        "modules_with_warnings": modules_with_warnings,
        "total_warnings": total_warnings,
        "validation_results": validation_results,
    }
