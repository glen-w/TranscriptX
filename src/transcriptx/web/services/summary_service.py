"""
Summary extraction service for analysis modules.

This service uses the plugin-based summary extractor system to
extract summaries from analysis data.
"""

from typing import Any, Dict

from transcriptx.web.summary_extractors import get_extractor
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


class SummaryService:
    """Service for extracting summaries from analysis data."""

    @staticmethod
    def extract_analysis_summary(
        module_name: str, analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract a summary with key metrics and highlights from analysis data.

        Args:
            module_name: Name of the analysis module
            analysis_data: The analysis data dictionary

        Returns:
            Dictionary with has_data, key_metrics, and highlights
        """
        if not analysis_data:
            return {"has_data": False, "key_metrics": {}, "highlights": []}

        summary = {"has_data": True, "key_metrics": {}, "highlights": []}

        try:
            # Get extractor for this module
            extractor = get_extractor(module_name)

            if extractor:
                # Use module-specific extractor
                extractor(analysis_data, summary)
            else:
                # Fallback to generic extractor
                logger.debug(
                    f"No extractor found for {module_name}, using generic extractor"
                )
                generic_extractor = get_extractor("__generic__")
                if generic_extractor:
                    generic_extractor(analysis_data, summary)
                else:
                    logger.warning(f"No extractor available for {module_name}")
                    summary["has_data"] = False
        except Exception as e:
            logger.warning(f"Failed to extract summary for {module_name}: {e}")
            summary["has_data"] = False

        return summary
