"""
Base data extractor for TranscriptX analysis modules.

This module provides a comprehensive base class for all data extractors,
eliminating code duplication and providing consistent patterns for
extracting, validating, and transforming analysis data.
"""

import json
import os
from abc import ABC, abstractmethod
from collections import Counter
from typing import Any, Dict, List, Optional

import numpy as np

from transcriptx.core.utils.logger import get_logger

logger = get_logger()


class BaseDataExtractor(ABC):
    """
    Abstract base class for all data extractors.

    This class provides common functionality for extracting data from analysis
    results, including validation, transformation, and aggregation methods.
    """

    def __init__(self, module_name: str):
        """
        Initialize the base data extractor.

        Args:
            module_name: Name of the analysis module this extractor handles
        """
        self.module_name = module_name
        self.logger = get_logger()

    @abstractmethod
    def extract_data(
        self, analysis_results: Dict[str, Any], speaker_id: str
    ) -> Dict[str, Any]:
        """
        Extract data from analysis results for a specific speaker.

        Args:
            analysis_results: Complete analysis results dictionary
            speaker_id: Speaker identifier

        Returns:
            Extracted data dictionary for the speaker
        """
        pass

    def validate_data(self, data: Dict[str, Any], speaker_id: str) -> bool:
        """
        Validate extracted data for a speaker.

        Args:
            data: Extracted data dictionary
            speaker_id: Speaker identifier

        Returns:
            True if data is valid, False otherwise
        """
        try:
            if not isinstance(data, dict):
                self.logger.warning(f"Invalid data type for {speaker_id}: {type(data)}")
                return False

            if not data:
                self.logger.warning(f"Empty data for {speaker_id}")
                return False

            # Check for required fields (subclasses can override)
            required_fields = self.get_required_fields()
            for field in required_fields:
                if field not in data:
                    self.logger.warning(
                        f"Missing required field '{field}' for {speaker_id}"
                    )
                    return False

            return True
        except Exception as e:
            self.logger.error(f"Data validation failed for {speaker_id}: {e}")
            return False

    def get_required_fields(self) -> List[str]:
        """
        Get list of required fields for this extractor.

        Returns:
            List of required field names
        """
        return []  # Subclasses can override

    def transform_data(self, data: Dict[str, Any], speaker_id: str) -> Dict[str, Any]:
        """
        Transform extracted data into standardized format.

        Args:
            data: Raw extracted data
            speaker_id: Speaker identifier

        Returns:
            Transformed data dictionary
        """
        try:
            transformed = {
                "speaker_id": speaker_id,
                "module": self.module_name,
                "extracted_at": self._get_timestamp(),
                "data": data,
            }

            # Add metadata
            transformed["metadata"] = self._extract_metadata(data)

            # Add quality metrics
            transformed["quality_metrics"] = self._calculate_quality_metrics(data)

            return transformed
        except Exception as e:
            self.logger.error(f"Data transformation failed for {speaker_id}: {e}")
            return {
                "speaker_id": speaker_id,
                "module": self.module_name,
                "error": str(e),
                "data": data,
            }

    def get_speaker_segments(
        self, analysis_results: Dict[str, Any], speaker_id: int | str
    ) -> List[Dict[str, Any]]:
        """
        Return segments belonging to a given speaker.

        This is a lightweight helper used by multiple extractors. It supports both the
        newer `speaker_db_id` field and older `speaker` string IDs.
        """
        segments = analysis_results.get("segments", [])
        if not isinstance(segments, list):
            return []

        # Normalize speaker_id to int if possible (for speaker_db_id matching)
        speaker_id_int: int | None = None
        try:
            speaker_id_int = int(speaker_id)  # type: ignore[arg-type]
        except Exception:
            speaker_id_int = None

        out: List[Dict[str, Any]] = []
        for seg in segments:
            if not isinstance(seg, dict):
                continue

            if (
                speaker_id_int is not None
                and seg.get("speaker_db_id") == speaker_id_int
            ):
                out.append(seg)
                continue

            if str(seg.get("speaker", "")) == str(speaker_id):
                out.append(seg)
                continue

        return out

    def calculate_average(self, values: List[float]) -> float:
        """Calculate average of numeric values (0.0 for empty)."""
        if not values:
            return 0.0
        try:
            return float(np.mean(values))
        except Exception:
            return 0.0

    def calculate_volatility(self, values: List[float]) -> float:
        """Calculate volatility (standard deviation; 0.0 for empty/degenerate)."""
        if not values:
            return 0.0
        try:
            return float(np.std(values))
        except Exception:
            return 0.0

    def safe_float(self, value: Any) -> Optional[float]:
        """Convert to float, returning None on failure."""
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    def get_most_frequent(self, items: List[Any]) -> Any:
        """Return most common item (or None if empty)."""
        if not items:
            return None
        try:
            return Counter(items).most_common(1)[0][0]
        except Exception:
            return None

    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime

        return datetime.now().isoformat()

    def _extract_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata from the data.

        Args:
            data: Extracted data dictionary

        Returns:
            Metadata dictionary
        """
        metadata = {
            "data_type": type(data).__name__,
            "data_size": len(str(data)),
            "has_numeric_data": self._has_numeric_data(data),
            "has_text_data": self._has_text_data(data),
            "has_list_data": self._has_list_data(data),
        }

        # Add field counts
        if isinstance(data, dict):
            metadata["field_count"] = len(data)
            metadata["field_types"] = {k: type(v).__name__ for k, v in data.items()}

        return metadata

    def _has_numeric_data(self, data: Any) -> bool:
        """Check if data contains numeric values."""
        if isinstance(data, (int, float)):
            return True
        elif isinstance(data, dict):
            return any(self._has_numeric_data(v) for v in data.values())
        elif isinstance(data, list):
            return any(self._has_numeric_data(v) for v in data)
        return False

    def _has_text_data(self, data: Any) -> bool:
        """Check if data contains text values."""
        if isinstance(data, str):
            return True
        elif isinstance(data, dict):
            return any(self._has_text_data(v) for v in data.values())
        elif isinstance(data, list):
            return any(self._has_text_data(v) for v in data)
        return False

    def _has_list_data(self, data: Any) -> bool:
        """Check if data contains list values."""
        if isinstance(data, list):
            return True
        elif isinstance(data, dict):
            return any(self._has_list_data(v) for v in data.values())
        return False

    def _calculate_quality_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate quality metrics for the extracted data.

        Args:
            data: Extracted data dictionary

        Returns:
            Quality metrics dictionary
        """
        metrics = {
            "completeness": self._calculate_completeness(data),
            "consistency": self._calculate_consistency(data),
            "validity": self._calculate_validity(data),
        }

        # Add specific metrics based on data type
        if self._has_numeric_data(data):
            metrics["numeric_quality"] = self._calculate_numeric_quality(data)

        if self._has_text_data(data):
            metrics["text_quality"] = self._calculate_text_quality(data)

        return metrics

    def _calculate_completeness(self, data: Dict[str, Any]) -> float:
        """Calculate data completeness score."""
        if not isinstance(data, dict):
            return 0.0

        required_fields = self.get_required_fields()
        if not required_fields:
            return 1.0  # No required fields means complete

        present_fields = sum(1 for field in required_fields if field in data)
        return present_fields / len(required_fields)

    def _calculate_consistency(self, data: Dict[str, Any]) -> float:
        """Calculate data consistency score."""
        if not isinstance(data, dict):
            return 0.0

        # Check for consistent data types
        type_consistency = 1.0
        for key, value in data.items():
            if isinstance(value, (dict, list)) and len(value) > 0:
                # Check if all items in collection have same type
                if isinstance(value, list):
                    types = set(type(item).__name__ for item in value)
                    if len(types) > 1:
                        type_consistency *= 0.8
                elif isinstance(value, dict):
                    # For dicts, check if all values have consistent types
                    value_types = set(type(v).__name__ for v in value.values())
                    if len(value_types) > 2:  # Allow some variation
                        type_consistency *= 0.9

        return type_consistency

    def _calculate_validity(self, data: Dict[str, Any]) -> float:
        """Calculate data validity score."""
        if not isinstance(data, dict):
            return 0.0

        # Check for obvious invalid values
        invalid_count = 0
        total_count = 0

        for key, value in data.items():
            total_count += 1
            if value is None:
                invalid_count += 1
            elif isinstance(value, str) and not value.strip():
                invalid_count += 1
            elif isinstance(value, (list, dict)) and not value:
                invalid_count += 1

        if total_count == 0:
            return 1.0

        return 1.0 - (invalid_count / total_count)

    def _calculate_numeric_quality(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate numeric data quality metrics."""
        numeric_values = []

        def extract_numeric_values(obj):
            if isinstance(obj, (int, float)):
                numeric_values.append(obj)
            elif isinstance(obj, dict):
                for v in obj.values():
                    extract_numeric_values(v)
            elif isinstance(obj, list):
                for item in obj:
                    extract_numeric_values(item)

        extract_numeric_values(data)

        if not numeric_values:
            return {"mean": 0.0, "std": 0.0, "range": 0.0}

        return {
            "mean": float(np.mean(numeric_values)),
            "std": float(np.std(numeric_values)),
            "range": float(max(numeric_values) - min(numeric_values)),
        }

    def _calculate_text_quality(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate text data quality metrics."""
        text_values = []

        def extract_text_values(obj):
            if isinstance(obj, str):
                text_values.append(obj)
            elif isinstance(obj, dict):
                for v in obj.values():
                    extract_text_values(v)
            elif isinstance(obj, list):
                for item in obj:
                    extract_text_values(item)

        extract_text_values(data)

        if not text_values:
            return {"avg_length": 0.0, "total_words": 0, "unique_words": 0}

        lengths = [len(text) for text in text_values]
        all_words = []
        for text in text_values:
            all_words.extend(text.split())

        return {
            "avg_length": float(np.mean(lengths)),
            "total_words": len(all_words),
            "unique_words": len(set(all_words)),
        }

    def aggregate_speaker_data(
        self, speaker_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregate data across multiple speakers.

        Args:
            speaker_data: Dictionary mapping speaker IDs to their extracted data

        Returns:
            Aggregated data dictionary
        """
        try:
            aggregated = {
                "module": self.module_name,
                "speaker_count": len(speaker_data),
                "aggregated_at": self._get_timestamp(),
                "speakers": list(speaker_data.keys()),
                "summary": self._create_summary(speaker_data),
                "patterns": self._extract_patterns(speaker_data),
                "statistics": self._calculate_statistics(speaker_data),
            }

            return aggregated
        except Exception as e:
            self.logger.error(f"Aggregation failed: {e}")
            return {
                "module": self.module_name,
                "error": str(e),
                "speaker_data": speaker_data,
            }

    def _create_summary(
        self, speaker_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create summary of speaker data."""
        summary = {
            "total_speakers": len(speaker_data),
            "successful_extractions": sum(
                1 for data in speaker_data.values() if "error" not in data
            ),
            "failed_extractions": sum(
                1 for data in speaker_data.values() if "error" in data
            ),
            "average_quality": 0.0,
        }

        # Calculate average quality
        quality_scores = []
        for data in speaker_data.values():
            if "quality_metrics" in data:
                metrics = data["quality_metrics"]
                avg_quality = np.mean(
                    [
                        metrics.get("completeness", 0),
                        metrics.get("consistency", 0),
                        metrics.get("validity", 0),
                    ]
                )
                quality_scores.append(avg_quality)

        if quality_scores:
            summary["average_quality"] = float(np.mean(quality_scores))

        return summary

    def _extract_patterns(
        self, speaker_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract patterns across speakers."""
        patterns = {
            "common_fields": set(),
            "field_frequency": Counter(),
            "data_types": Counter(),
        }

        for speaker_id, data in speaker_data.items():
            if "data" in data and isinstance(data["data"], dict):
                # Track common fields
                patterns["common_fields"].update(data["data"].keys())

                # Track field frequency
                for field in data["data"].keys():
                    patterns["field_frequency"][field] += 1

                # Track data types
                for value in data["data"].values():
                    patterns["data_types"][type(value).__name__] += 1

        # Convert sets to lists for JSON serialization
        patterns["common_fields"] = list(patterns["common_fields"])
        patterns["field_frequency"] = dict(patterns["field_frequency"])
        patterns["data_types"] = dict(patterns["data_types"])

        return patterns

    def _calculate_statistics(
        self, speaker_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate statistical measures across speakers."""
        stats = {"data_sizes": [], "quality_scores": [], "extraction_times": []}

        for data in speaker_data.values():
            # Data sizes
            if "metadata" in data and "data_size" in data["metadata"]:
                stats["data_sizes"].append(data["metadata"]["data_size"])

            # Quality scores
            if "quality_metrics" in data:
                metrics = data["quality_metrics"]
                avg_quality = np.mean(
                    [
                        metrics.get("completeness", 0),
                        metrics.get("consistency", 0),
                        metrics.get("validity", 0),
                    ]
                )
                stats["quality_scores"].append(avg_quality)

        # Calculate summary statistics
        summary_stats = {}
        for key, values in stats.items():
            if values:
                summary_stats[key] = {
                    "mean": float(np.mean(values)),
                    "std": float(np.std(values)),
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                    "count": len(values),
                }
            else:
                summary_stats[key] = {
                    "mean": 0.0,
                    "std": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "count": 0,
                }

        return summary_stats

    def save_extracted_data(self, data: Dict[str, Any], output_path: str) -> bool:
        """
        Save extracted data to file.

        Args:
            data: Extracted data to save
            output_path: Path where to save the data

        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Save as JSON
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            self.logger.info(f"✅ Saved extracted data to {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to save extracted data: {e}")
            return False

    def load_extracted_data(self, input_path: str) -> Optional[Dict[str, Any]]:
        """
        Load extracted data from file.

        Args:
            input_path: Path to the data file

        Returns:
            Loaded data dictionary or None if failed
        """
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.logger.info(f"✅ Loaded extracted data from {input_path}")
            return data
        except Exception as e:
            self.logger.error(f"❌ Failed to load extracted data: {e}")
            return None
