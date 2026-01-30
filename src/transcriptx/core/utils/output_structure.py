"""
Standardized and configurable output directory structure.

This module provides a unified system for managing output directory structures,
making them configurable and testable.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import OUTPUTS_DIR

logger = get_logger()


@dataclass
class OutputStructureConfig:
    """
    Configuration for output directory structure.

    This allows users to customize the output directory layout
    while maintaining consistency.
    """

    # Base directory structure
    base_output_dir: str = OUTPUTS_DIR
    create_subdirectories: bool = True  # If False, use flat structure

    # Directory naming patterns
    transcript_dir_pattern: str = "{base_name}"  # Pattern for transcript directory
    module_dir_pattern: str = (
        "{transcript_dir}/{module_name}"  # Pattern for module directory
    )

    # Subdirectory structure
    use_data_dir: bool = True
    use_charts_dir: bool = True
    use_global_subdirs: bool = True  # Create global/ and speakers/ subdirs
    use_speaker_subdirs: bool = True

    # Additional directories
    extra_dirs: list[str] = field(default_factory=list)  # Additional custom directories

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate the output structure configuration.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check base directory is valid
        try:
            base_path = Path(self.base_output_dir)
            if not base_path.parent.exists():
                errors.append(
                    f"Base output directory parent does not exist: {base_path.parent}"
                )
        except Exception as e:
            errors.append(f"Invalid base output directory: {e}")

        # Check patterns contain required placeholders
        required_placeholders = {"base_name", "module_name", "transcript_dir"}
        if "{base_name}" not in self.transcript_dir_pattern:
            errors.append("transcript_dir_pattern must contain {base_name}")
        if "{module_name}" not in self.module_dir_pattern:
            errors.append("module_dir_pattern must contain {module_name}")

        return len(errors) == 0, errors


@dataclass
class OutputStructure:
    """
    Standardized output directory structure for a module.

    This class provides a consistent interface for accessing output directories,
    regardless of the underlying structure configuration.
    """

    # Core directories
    transcript_dir: str
    module_dir: str

    # Data directories
    data_dir: Optional[str] = None
    global_data_dir: Optional[str] = None
    speaker_data_dir: Optional[str] = None

    # Chart directories
    charts_dir: Optional[str] = None
    global_charts_dir: Optional[str] = None
    speaker_charts_dir: Optional[str] = None

    # Additional directories
    extra_dirs: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate that the output structure is properly configured.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required directories exist
        required = [self.transcript_dir, self.module_dir]
        for dir_path in required:
            if not dir_path:
                errors.append(f"Required directory not set: {dir_path}")

        # Check directory structure is consistent
        if self.data_dir and not self.data_dir.startswith(self.module_dir):
            errors.append(f"data_dir must be within module_dir: {self.data_dir}")

        if self.charts_dir and not self.charts_dir.startswith(self.module_dir):
            errors.append(f"charts_dir must be within module_dir: {self.charts_dir}")

        return len(errors) == 0, errors

    def create_directories(self) -> None:
        """Create all directories in the structure."""
        directories = [
            self.transcript_dir,
            self.module_dir,
            self.data_dir,
            self.charts_dir,
            self.global_data_dir,
            self.global_charts_dir,
            self.speaker_data_dir,
            self.speaker_charts_dir,
        ]

        # Add extra directories
        directories.extend(self.extra_dirs.values())

        for dir_path in directories:
            if dir_path:
                Path(dir_path).mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, str]:
        """Convert structure to dictionary."""
        result = {
            "transcript_dir": self.transcript_dir,
            "module_dir": self.module_dir,
        }

        if self.data_dir:
            result["data_dir"] = self.data_dir
        if self.charts_dir:
            result["charts_dir"] = self.charts_dir
        if self.global_data_dir:
            result["global_data_dir"] = self.global_data_dir
        if self.global_charts_dir:
            result["global_charts_dir"] = self.global_charts_dir
        if self.speaker_data_dir:
            result["speaker_data_dir"] = self.speaker_data_dir
        if self.speaker_charts_dir:
            result["speaker_charts_dir"] = self.speaker_charts_dir

        result.update(self.extra_dirs)

        return result


class OutputStructureBuilder:
    """
    Builder for creating standardized output structures.

    This class uses the OutputStructureConfig to create consistent
    output directory structures across all modules.
    """

    def __init__(self, config: Optional[OutputStructureConfig] = None):
        """
        Initialize output structure builder.

        Args:
            config: Output structure configuration (default: from global config)
        """
        if config is None:
            config = self._load_config_from_settings()
        self.config = config

        # Validate config
        is_valid, errors = config.validate()
        if not is_valid:
            logger.warning(f"Output structure config has errors: {errors}")

    def _load_config_from_settings(self) -> OutputStructureConfig:
        """Load output structure config from global settings."""
        try:
            app_config = get_config()
            return OutputStructureConfig(
                base_output_dir=(
                    app_config.output.base_output_dir
                    if hasattr(app_config, "output")
                    else OUTPUTS_DIR
                ),
                create_subdirectories=(
                    app_config.output.create_subdirectories
                    if hasattr(app_config, "output")
                    else True
                ),
            )
        except Exception as e:
            logger.warning(f"Failed to load output config, using defaults: {e}")
            return OutputStructureConfig()

    def create_structure(
        self, transcript_path: str, module_name: str, base_name: Optional[str] = None
    ) -> OutputStructure:
        """
        Create output structure for a module.

        Args:
            transcript_path: Path to transcript file
            module_name: Name of the analysis module
            base_name: Base name for directory (default: extracted from transcript_path)

        Returns:
            OutputStructure object
        """
        # Extract base name if not provided
        if base_name is None:
            base_name = Path(transcript_path).stem

        # Build transcript directory
        transcript_dir = self.config.transcript_dir_pattern.format(
            base_name=base_name, base_output_dir=self.config.base_output_dir
        )

        # Build module directory
        module_dir = self.config.module_dir_pattern.format(
            transcript_dir=transcript_dir, module_name=module_name, base_name=base_name
        )

        # Create structure
        structure = OutputStructure(
            transcript_dir=transcript_dir, module_dir=module_dir
        )

        # Add data directories if enabled
        if self.config.use_data_dir:
            structure.data_dir = str(Path(module_dir) / "data")

            if self.config.use_global_subdirs:
                structure.global_data_dir = str(Path(structure.data_dir) / "global")

            if self.config.use_speaker_subdirs:
                structure.speaker_data_dir = str(Path(structure.data_dir) / "speakers")

        # Add chart directories if enabled
        if self.config.use_charts_dir:
            structure.charts_dir = str(Path(module_dir) / "charts")

            if self.config.use_global_subdirs:
                structure.global_charts_dir = str(Path(structure.charts_dir) / "global")

            if self.config.use_speaker_subdirs:
                structure.speaker_charts_dir = str(
                    Path(structure.charts_dir) / "speakers"
                )

        # Add extra directories
        for extra_dir_name in self.config.extra_dirs:
            structure.extra_dirs[extra_dir_name] = str(
                Path(module_dir) / extra_dir_name
            )

        # Validate structure
        is_valid, errors = structure.validate()
        if not is_valid:
            logger.warning(f"Output structure validation errors: {errors}")

        # Create directories
        structure.create_directories()

        return structure


# Global builder instance
_default_builder: Optional[OutputStructureBuilder] = None


def get_output_structure_builder() -> OutputStructureBuilder:
    """Get the default output structure builder."""
    global _default_builder
    if _default_builder is None:
        _default_builder = OutputStructureBuilder()
    return _default_builder


def create_output_structure(
    transcript_path: str, module_name: str, base_name: Optional[str] = None
) -> OutputStructure:
    """
    Create output structure for a module (convenience function).

    Args:
        transcript_path: Path to transcript file
        module_name: Name of the analysis module
        base_name: Base name for directory (default: extracted from transcript_path)

    Returns:
        OutputStructure object
    """
    builder = get_output_structure_builder()
    return builder.create_structure(transcript_path, module_name, base_name)
