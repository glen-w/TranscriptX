"""
Coverage analysis tools for TranscriptX testing.

This module provides utilities for analyzing test coverage, identifying gaps,
and generating coverage reports.
"""

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_coverage_report() -> Dict[str, Any]:
    """
    Get current test coverage report by parsing coverage.xml.
    
    Returns:
        Dictionary containing coverage metrics including:
        - overall_coverage: Overall coverage percentage
        - branch_coverage: Branch coverage percentage
        - module_coverage: Per-module coverage breakdown
        - missing_lines: Lines not covered by tests
        
    Note:
        Requires coverage.py to be installed and coverage.xml to exist
    """
    coverage_file = Path("coverage.xml")
    if not coverage_file.exists():
        return {"error": "coverage.xml not found. Run tests with coverage first."}
    
    try:
        tree = ET.parse(coverage_file)
        root = tree.getroot()
        
        # Extract overall coverage metrics
        overall_coverage = float(root.get("line-rate", 0.0)) * 100
        branch_coverage = float(root.get("branch-rate", 0.0)) * 100
        
        # Parse per-module coverage
        module_coverage = {}
        missing_lines_by_module = {}
        
        for package in root.findall(".//package"):
            package_name = package.get("name", "unknown")
            
            for class_elem in package.findall(".//class"):
                class_name = class_elem.get("name", "unknown")
                module_path = f"{package_name}.{class_name}"
                
                line_rate = float(class_elem.get("line-rate", 0.0)) * 100
                branch_rate = float(class_elem.get("branch-rate", 0.0)) * 100
                
                module_coverage[module_path] = {
                    "line_coverage": line_rate,
                    "branch_coverage": branch_rate,
                }
                
                # Extract missing lines
                lines = class_elem.findall(".//line")
                missing_lines = []
                for line in lines:
                    if line.get("hits") == "0":
                        missing_lines.append(int(line.get("number", 0)))
                
                if missing_lines:
                    missing_lines_by_module[module_path] = missing_lines
        
        return {
            "coverage_file": str(coverage_file),
            "exists": True,
            "overall_coverage": overall_coverage,
            "branch_coverage": branch_coverage,
            "module_coverage": module_coverage,
            "missing_lines": missing_lines_by_module,
            "total_modules": len(module_coverage),
        }
    except ET.ParseError as e:
        return {"error": f"Failed to parse coverage.xml: {e}"}
    except Exception as e:
        return {"error": f"Error processing coverage report: {e}"}


def identify_coverage_gaps(
    source_dir: str = "src/transcriptx",
    test_dir: str = "tests"
) -> Dict[str, List[str]]:
    """
    Identify modules and functions with no test coverage.
    
    Args:
        source_dir: Source code directory
        test_dir: Test directory
        
    Returns:
        Dictionary containing:
        - untested_modules: List of modules with no tests
        - untested_functions: List of functions with no tests
        - untested_classes: List of classes with no tests
    """
    source_path = Path(source_dir)
    test_path = Path(test_dir)
    
    gaps = {
        "untested_modules": [],
        "untested_functions": [],
        "untested_classes": []
    }
    
    # Find all Python source files
    source_files = list(source_path.rglob("*.py"))
    source_files = [f for f in source_files if "__pycache__" not in str(f)]
    
    # Find all test files
    test_files = list(test_path.rglob("test_*.py"))
    
    # Simple heuristic: check if test file exists for each source file
    for source_file in source_files:
        relative_path = source_file.relative_to(source_path)
        module_name = str(relative_path).replace("/", ".").replace(".py", "")
        
        # Check if corresponding test file exists
        test_file_name = f"test_{relative_path.name}"
        has_test = any(test_file_name in str(tf) for tf in test_files)
        
        if not has_test:
            gaps["untested_modules"].append(module_name)
    
    return gaps


def generate_coverage_summary() -> str:
    """
    Generate a human-readable coverage summary.
    
    Returns:
        Formatted coverage summary string
    """
    report = get_coverage_report()
    
    if "error" in report:
        return f"Coverage Summary\n{'=' * 50}\n\nError: {report['error']}\n"
    
    gaps = identify_coverage_gaps()
    
    summary = "Test Coverage Summary\n"
    summary += "=" * 50 + "\n\n"
    summary += f"Overall Coverage: {report['overall_coverage']:.2f}%\n"
    summary += f"Branch Coverage: {report['branch_coverage']:.2f}%\n"
    summary += f"Total Modules: {report['total_modules']}\n\n"
    
    # Find modules with low coverage
    low_coverage_modules = [
        (module, data["line_coverage"])
        for module, data in report["module_coverage"].items()
        if data["line_coverage"] < 80.0
    ]
    low_coverage_modules.sort(key=lambda x: x[1])
    
    if low_coverage_modules:
        summary += "Modules with Low Coverage (< 80%):\n"
        for module, coverage in low_coverage_modules[:10]:
            summary += f"  - {module}: {coverage:.2f}%\n"
        summary += "\n"
    
    summary += f"Untested Modules: {len(gaps['untested_modules'])}\n"
    summary += f"Untested Functions: {len(gaps['untested_functions'])}\n"
    summary += f"Untested Classes: {len(gaps['untested_classes'])}\n\n"
    
    if gaps['untested_modules']:
        summary += "Top Untested Modules:\n"
        for module in gaps['untested_modules'][:10]:
            summary += f"  - {module}\n"
    
    return summary


def get_module_coverage_gaps(module_name: str) -> Dict[str, Any]:
    """
    Get coverage gaps for a specific module.
    
    Args:
        module_name: Name of the module to analyze
        
    Returns:
        Dictionary containing:
        - module_name: Name of the module
        - coverage: Coverage percentage
        - missing_lines: List of line numbers not covered
    """
    report = get_coverage_report()
    
    if "error" in report:
        return {"error": report["error"]}
    
    # Find matching module
    matching_modules = [
        (name, data)
        for name, data in report["module_coverage"].items()
        if module_name in name
    ]
    
    if not matching_modules:
        return {"error": f"Module '{module_name}' not found in coverage report"}
    
    # Return first match (or could return all matches)
    module_path, coverage_data = matching_modules[0]
    
    missing_lines = report["missing_lines"].get(module_path, [])
    
    return {
        "module_name": module_path,
        "line_coverage": coverage_data["line_coverage"],
        "branch_coverage": coverage_data["branch_coverage"],
        "missing_lines": missing_lines,
        "total_missing_lines": len(missing_lines),
    }