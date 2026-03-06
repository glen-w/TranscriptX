"""
Summary extractors for analysis modules.

This package provides a plugin system for extracting summaries from
analysis module output data. Each module can have its own extractor.
"""

import importlib
from typing import Dict, Any, Optional, Callable
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

# Registry of summary extractors
_extractors: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], None]] = {}


def register_extractor(
    module_name: str, extractor_func: Callable[[Dict[str, Any], Dict[str, Any]], None]
) -> None:
    """
    Register a summary extractor for a module.

    Args:
        module_name: Name of the analysis module
        extractor_func: Function that extracts summary from analysis data
                        Signature: (data: Dict, summary: Dict) -> None
                        The function should populate summary["key_metrics"] and summary["highlights"]
    """
    _extractors[module_name] = extractor_func
    logger.debug(f"Registered summary extractor for module: {module_name}")


def get_extractor(
    module_name: str,
) -> Optional[Callable[[Dict[str, Any], Dict[str, Any]], None]]:
    """
    Get the extractor function for a module.

    Args:
        module_name: Name of the analysis module

    Returns:
        Extractor function or None if not found
    """
    return _extractors.get(module_name)


def has_extractor(module_name: str) -> bool:
    """
    Check if an extractor is registered for a module.

    Args:
        module_name: Name of the analysis module

    Returns:
        True if extractor exists, False otherwise
    """
    return module_name in _extractors


# Import all extractors to register them (lazy import to avoid circular dependencies)
def _register_all_extractors():
    """Register all extractors by importing them."""
    module_names = (
        "sentiment",
        "emotion",
        "topic_modeling",
        "ner",
        "acts",
        "stats",
        "contagion",
        "tics",
        "interactions",
        "semantic_similarity",
        "entity_sentiment",
        "understandability",
        "temporal_dynamics",
        "qa_analysis",
        "generic",
    )
    for module_name in module_names:
        importlib.import_module(f"{__name__}.{module_name}")


# Auto-register on import
_register_all_extractors()

__all__ = [
    "register_extractor",
    "get_extractor",
    "has_extractor",
]
