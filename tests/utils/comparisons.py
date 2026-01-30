"""
Comparison utilities for TranscriptX testing.

This module provides functions for comparing test results, transcripts,
speaker maps, and other data structures to validate correctness.
"""

from typing import Any, Dict, List, Optional


def compare_transcripts(
    transcript1: Dict[str, Any],
    transcript2: Dict[str, Any],
    ignore_timestamps: bool = False,
    ignore_speaker_order: bool = False
) -> Dict[str, Any]:
    """
    Compare two transcripts and return differences.
    
    Args:
        transcript1: First transcript to compare
        transcript2: Second transcript to compare
        ignore_timestamps: If True, ignore timestamp differences
        ignore_speaker_order: If True, ignore order of segments
        
    Returns:
        Dictionary containing comparison results:
        - equal: Whether transcripts are equal
        - differences: List of differences found
        - segment_count_diff: Difference in segment counts
    """
    differences = []
    
    segments1 = transcript1.get("segments", [])
    segments2 = transcript2.get("segments", [])
    
    if len(segments1) != len(segments2):
        differences.append(f"Segment count differs: {len(segments1)} vs {len(segments2)}")
    
    if ignore_speaker_order:
        # Sort segments by speaker and text for comparison
        segments1 = sorted(segments1, key=lambda s: (s.get("speaker", ""), s.get("text", "")))
        segments2 = sorted(segments2, key=lambda s: (s.get("speaker", ""), s.get("text", "")))
    
    min_len = min(len(segments1), len(segments2))
    for i in range(min_len):
        seg1 = segments1[i]
        seg2 = segments2[i]
        
        if seg1.get("speaker") != seg2.get("speaker"):
            differences.append(f"Segment {i}: speaker differs ({seg1.get('speaker')} vs {seg2.get('speaker')})")
        
        if seg1.get("text") != seg2.get("text"):
            differences.append(f"Segment {i}: text differs")
        
        if not ignore_timestamps:
            if seg1.get("start") != seg2.get("start"):
                differences.append(f"Segment {i}: start time differs")
            if seg1.get("end") != seg2.get("end"):
                differences.append(f"Segment {i}: end time differs")
    
    return {
        "equal": len(differences) == 0,
        "differences": differences,
        "segment_count_diff": len(segments1) - len(segments2)
    }


def compare_speaker_maps(
    map1: Dict[str, str],
    map2: Dict[str, str]
) -> Dict[str, Any]:
    """
    Compare two speaker maps and return differences.
    
    Args:
        map1: First speaker map
        map2: Second speaker map
        
    Returns:
        Dictionary containing comparison results
    """
    differences = []
    
    keys1 = set(map1.keys())
    keys2 = set(map2.keys())
    
    missing_in_map2 = keys1 - keys2
    missing_in_map1 = keys2 - keys1
    common_keys = keys1 & keys2
    
    if missing_in_map2:
        differences.append(f"Keys in map1 but not map2: {missing_in_map2}")
    if missing_in_map1:
        differences.append(f"Keys in map2 but not map1: {missing_in_map1}")
    
    for key in common_keys:
        if map1[key] != map2[key]:
            differences.append(f"Key '{key}': '{map1[key]}' vs '{map2[key]}'")
    
    return {
        "equal": len(differences) == 0,
        "differences": differences,
        "common_keys": len(common_keys),
        "unique_to_map1": len(missing_in_map2),
        "unique_to_map2": len(missing_in_map1)
    }


def compare_analysis_results(
    result1: Dict[str, Any],
    result2: Dict[str, Any],
    tolerance: float = 0.001
) -> Dict[str, Any]:
    """
    Compare two analysis results and return differences.
    
    Args:
        result1: First analysis result
        result2: Second analysis result
        tolerance: Tolerance for floating point comparisons
        
    Returns:
        Dictionary containing comparison results
    """
    differences = []
    
    # Compare module names
    if result1.get("module_name") != result2.get("module_name"):
        differences.append("Module names differ")
    
    # Compare status
    if result1.get("status") != result2.get("status"):
        differences.append(f"Status differs: {result1.get('status')} vs {result2.get('status')}")
    
    # Compare result data (recursive comparison)
    data1 = result1.get("result_data", {})
    data2 = result2.get("result_data", {})
    
    data_diff = compare_dicts_recursive(data1, data2, tolerance=tolerance)
    if data_diff["differences"]:
        differences.extend([f"Result data: {d}" for d in data_diff["differences"]])
    
    return {
        "equal": len(differences) == 0,
        "differences": differences
    }


def compare_dicts_recursive(
    dict1: Dict[str, Any],
    dict2: Dict[str, Any],
    tolerance: float = 0.001,
    path: str = ""
) -> Dict[str, Any]:
    """
    Recursively compare two dictionaries.
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary
        tolerance: Tolerance for floating point comparisons
        path: Current path in dictionary (for error messages)
        
    Returns:
        Dictionary containing comparison results
    """
    differences = []
    
    keys1 = set(dict1.keys())
    keys2 = set(dict2.keys())
    
    missing_in_dict2 = keys1 - keys2
    missing_in_dict1 = keys2 - keys1
    
    if missing_in_dict2:
        differences.append(f"{path}: Keys in dict1 but not dict2: {missing_in_dict2}")
    if missing_in_dict1:
        differences.append(f"{path}: Keys in dict2 but not dict1: {missing_in_dict1}")
    
    for key in keys1 & keys2:
        current_path = f"{path}.{key}" if path else key
        val1 = dict1[key]
        val2 = dict2[key]
        
        if isinstance(val1, dict) and isinstance(val2, dict):
            nested_diff = compare_dicts_recursive(val1, val2, tolerance, current_path)
            differences.extend(nested_diff["differences"])
        elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            if abs(val1 - val2) > tolerance:
                differences.append(f"{current_path}: Values differ: {val1} vs {val2}")
        elif val1 != val2:
            differences.append(f"{current_path}: Values differ: {val1} vs {val2}")
    
    return {
        "equal": len(differences) == 0,
        "differences": differences
    }


def assert_dicts_equal(
    dict1: Dict[str, Any],
    dict2: Dict[str, Any],
    tolerance: float = 0.001,
    msg: Optional[str] = None
) -> None:
    """
    Assert that two dictionaries are equal (with optional tolerance for floats).
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary
        tolerance: Tolerance for floating point comparisons
        msg: Optional error message
        
    Raises:
        AssertionError: If dictionaries are not equal
    """
    comparison = compare_dicts_recursive(dict1, dict2, tolerance)
    if not comparison["equal"]:
        error_msg = msg or "Dictionaries are not equal"
        error_msg += f"\nDifferences: {comparison['differences']}"
        raise AssertionError(error_msg)


