"""
Module registry for TranscriptX web interface.

This module provides dynamic module discovery for the web interface,
leveraging the core pipeline module registry as the source of truth.
"""

from typing import List, Optional

from transcriptx.core.pipeline.module_registry import (
    get_available_modules as get_core_modules,
    get_module_info,
)
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def get_analysis_modules(session_name: str) -> List[str]:
    """
    List available analysis modules for a session by scanning filesystem.

    This function dynamically discovers modules by:
    1. Getting the list of all available modules from the core registry
    2. Checking which modules have output directories for the given session

    Args:
        session_name: Name of the session

    Returns:
        List of module names that have output for this session
    """
    # Import here to avoid circular dependency
    from transcriptx.web.services.file_service import FileService
    
    modules = []
    session_dir = FileService._resolve_session_dir(session_name)

    if not session_dir.exists():
        return modules

    # Get all available modules from core registry
    available_modules = get_core_modules()

    # Check which modules have output directories
    for module_name in available_modules:
        module_dir = session_dir / module_name
        if module_dir.exists() and module_dir.is_dir():
            modules.append(module_name)

    return sorted(modules)


def get_all_available_modules() -> List[str]:
    """
    Get list of all available analysis modules from the core registry.

    Returns:
        List of all module names
    """
    return get_core_modules()


def get_total_module_count() -> int:
    """
    Get the total number of available analysis modules.

    This replaces the hardcoded magic number and dynamically
    calculates based on the core registry.

    Returns:
        Total number of available modules
    """
    return len(get_core_modules())


def is_module_available(module_name: str) -> bool:
    """
    Check if a module is available in the core registry.

    Args:
        module_name: Name of the module to check

    Returns:
        True if module is available, False otherwise
    """
    return module_name in get_core_modules()


def get_module_metadata(module_name: str) -> Optional[dict]:
    """
    Get metadata for a module from the core registry.

    Args:
        module_name: Name of the module

    Returns:
        Dictionary with module metadata or None if not found
    """
    module_info = get_module_info(module_name)
    if not module_info:
        return None

    return {
        "name": module_info.name,
        "description": module_info.description,
        "category": module_info.category,
        "dependencies": module_info.dependencies,
    }
