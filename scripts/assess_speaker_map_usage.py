#!/usr/bin/env python3
"""
Assessment script to catalog all speaker_map usage in the codebase.

This script scans the codebase for all patterns related to speaker_map usage
and generates a comprehensive report for migration planning.
"""

import ast
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
import json

# Patterns to search for
PATTERNS = {
    "function_param": r"speaker_map\s*[:=]",
    "load_speaker_map": r"load_speaker_map\s*\(",
    "build_speaker_map": r"build_speaker_map\s*\(",
    "speaker_map_get": r"speaker_map\.get\s*\(",
    "speaker_map_lookup": r"speaker_map\[",
    "speaker_map_path": r"speaker_map_path",
    "get_speaker_map_path": r"get_speaker_map_path\s*\(",
    "validate_speaker_map": r"validate_speaker_map\s*\(",
    "save_speaker_map": r"save_speaker_map\s*\(",
}

# Directories to scan
SOURCE_DIRS = [
    "src/transcriptx",
    "tests",
    "scripts",
]

# Files to exclude
EXCLUDE_PATTERNS = [
    "__pycache__",
    ".pyc",
    ".pyo",
    ".pyd",
    ".egg-info",
    "archived",
    "deprecated",
    ".git",
    "node_modules",
    "venv",
    "env",
    ".pytest_cache",
]


class SpeakerMapUsageFinder(ast.NodeVisitor):
    """AST visitor to find speaker_map usage patterns."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.usages = []
        self.function_params = []
        self.imports = []
        self.current_function = None
        
    def visit_FunctionDef(self, node):
        """Track function definitions and their parameters."""
        old_function = self.current_function
        self.current_function = node.name
        
        # Check function parameters
        for arg in node.args.args:
            if arg.arg == "speaker_map":
                self.function_params.append({
                    "function": node.name,
                    "line": node.lineno,
                    "col": node.col_offset,
                })
        
        self.generic_visit(node)
        self.current_function = old_function
    
    def visit_Import(self, node):
        """Track imports."""
        for alias in node.names:
            if "speaker_map" in alias.name.lower() or "speaker_mapping" in alias.name.lower():
                self.imports.append({
                    "module": alias.name,
                    "line": node.lineno,
                    "alias": alias.asname,
                })
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """Track from imports."""
        for alias in node.names:
            if "speaker_map" in alias.name.lower() or "speaker_mapping" in alias.name.lower():
                self.imports.append({
                    "module": node.module or "",
                    "name": alias.name,
                    "line": node.lineno,
                    "alias": alias.asname,
                })
        self.generic_visit(node)
    
    def visit_Call(self, node):
        """Track function calls related to speaker_map."""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if "speaker_map" in func_name.lower():
                self.usages.append({
                    "type": "function_call",
                    "name": func_name,
                    "line": node.lineno,
                    "col": node.col_offset,
                    "function": self.current_function,
                })
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if "speaker_map" in attr_name.lower():
                self.usages.append({
                    "type": "method_call",
                    "name": attr_name,
                    "line": node.lineno,
                    "col": node.col_offset,
                    "function": self.current_function,
                })
        self.generic_visit(node)
    
    def visit_Subscript(self, node):
        """Track dictionary lookups."""
        if isinstance(node.value, ast.Name) and node.value.id == "speaker_map":
            self.usages.append({
                "type": "dict_lookup",
                "line": node.lineno,
                "col": node.col_offset,
                "function": self.current_function,
            })
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        """Track attribute access."""
        if isinstance(node.value, ast.Name) and node.value.id == "speaker_map":
            self.usages.append({
                "type": "attribute_access",
                "name": node.attr,
                "line": node.lineno,
                "col": node.col_offset,
                "function": self.current_function,
            })
        self.generic_visit(node)


def should_exclude_file(file_path: str) -> bool:
    """Check if file should be excluded from scanning."""
    path_str = str(file_path)
    return any(pattern in path_str for pattern in EXCLUDE_PATTERNS)


def scan_file(file_path: Path) -> Dict[str, Any]:
    """Scan a single file for speaker_map usage."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return {"error": str(e)}
    
    # Regex-based pattern matching
    regex_matches = {}
    for pattern_name, pattern in PATTERNS.items():
        matches = list(re.finditer(pattern, content))
        if matches:
            regex_matches[pattern_name] = [
                {"line": content[:m.start()].count("\n") + 1, "match": m.group()}
                for m in matches
            ]
    
    # AST-based analysis
    ast_matches = {
        "function_params": [],
        "imports": [],
        "usages": [],
    }
    
    try:
        tree = ast.parse(content, filename=str(file_path))
        finder = SpeakerMapUsageFinder(str(file_path))
        finder.visit(tree)
        ast_matches["function_params"] = finder.function_params
        ast_matches["imports"] = finder.imports
        ast_matches["usages"] = finder.usages
    except SyntaxError:
        # Skip files with syntax errors
        pass
    except Exception as e:
        ast_matches["error"] = str(e)
    
    # Combine results
    result = {
        "file": str(file_path),
        "regex_matches": regex_matches,
        "ast_matches": ast_matches,
    }
    
    # Determine if file has any usage
    has_usage = bool(regex_matches) or bool(ast_matches["function_params"]) or \
                bool(ast_matches["imports"]) or bool(ast_matches["usages"])
    
    result["has_usage"] = has_usage
    
    return result


def classify_priority(file_path: str, results: Dict[str, Any]) -> str:
    """Classify file priority based on usage patterns."""
    path_str = str(file_path).lower()
    
    # High priority: core analysis modules, I/O functions
    if any(x in path_str for x in [
        "core/analysis/",
        "io/file_io.py",
        "core/utils/transcript_output.py",
        "core/analysis/common.py",
    ]):
        return "HIGH"
    
    # Medium priority: pipeline, CLI, tests
    if any(x in path_str for x in [
        "core/pipeline/",
        "cli/",
        "tests/",
    ]):
        return "MEDIUM"
    
    # Low priority: everything else
    return "LOW"


def categorize_file(file_path: str) -> str:
    """Categorize file into migration category."""
    path_str = str(file_path).lower()
    
    if "core/analysis/" in path_str:
        return "A: Analysis Modules"
    elif "io/" in path_str or "core/utils/" in path_str:
        return "B: I/O and Utilities"
    elif "core/pipeline/" in path_str:
        return "C: Pipeline Infrastructure"
    elif "cli/" in path_str:
        return "D: CLI and Workflows"
    elif "database/" in path_str:
        return "E: Database and Ingestion"
    elif "tests/" in path_str:
        return "F: Test Files"
    elif "core/utils/state" in path_str or "core/utils/run_manifest" in path_str:
        return "G: State and Configuration"
    else:
        return "Other"


def generate_report(results: List[Dict[str, Any]]) -> str:
    """Generate markdown report from scan results."""
    # Group by category
    by_category = defaultdict(list)
    by_priority = defaultdict(list)
    
    for result in results:
        if not result.get("has_usage"):
            continue
        
        file_path = result["file"]
        category = categorize_file(file_path)
        priority = classify_priority(file_path, result)
        
        by_category[category].append(result)
        by_priority[priority].append(result)
    
    # Generate report
    report_lines = [
        "# Speaker Map Usage Assessment Report",
        "",
        "## Summary",
        "",
        f"- **Total files scanned**: {len(results)}",
        f"- **Files with speaker_map usage**: {len([r for r in results if r.get('has_usage')])}",
        f"- **High priority files**: {len(by_priority['HIGH'])}",
        f"- **Medium priority files**: {len(by_priority['MEDIUM'])}",
        f"- **Low priority files**: {len(by_priority['LOW'])}",
        "",
        "## Files by Priority",
        "",
    ]
    
    for priority in ["HIGH", "MEDIUM", "LOW"]:
        if by_priority[priority]:
            report_lines.append(f"### {priority} Priority ({len(by_priority[priority])} files)")
            report_lines.append("")
            for result in sorted(by_priority[priority], key=lambda x: x["file"]):
                file_path = result["file"]
                category = categorize_file(file_path)
                report_lines.append(f"- `{file_path}` ({category})")
            report_lines.append("")
    
    report_lines.append("## Detailed File Analysis")
    report_lines.append("")
    
    for category in sorted(by_category.keys()):
        files = by_category[category]
        if not files:
            continue
        
        report_lines.append(f"### {category}")
        report_lines.append("")
        
        for result in sorted(files, key=lambda x: x["file"]):
            file_path = result["file"]
            report_lines.append(f"#### `{file_path}`")
            report_lines.append("")
            
            # Function parameters
            if result["ast_matches"]["function_params"]:
                report_lines.append("**Function Parameters:**")
                for param in result["ast_matches"]["function_params"]:
                    report_lines.append(f"- `{param['function']}()` accepts `speaker_map` parameter (line {param['line']})")
                report_lines.append("")
            
            # Imports
            if result["ast_matches"]["imports"]:
                report_lines.append("**Imports:**")
                for imp in result["ast_matches"]["imports"]:
                    if "module" in imp:
                        report_lines.append(f"- Import from `{imp['module']}` (line {imp['line']})")
                    elif "name" in imp:
                        report_lines.append(f"- Import `{imp['name']}` from `{imp['module']}` (line {imp['line']})")
                report_lines.append("")
            
            # Usage patterns
            if result["regex_matches"]:
                report_lines.append("**Usage Patterns:**")
                for pattern_name, matches in result["regex_matches"].items():
                    report_lines.append(f"- {pattern_name}: {len(matches)} occurrence(s)")
                    for match in matches[:5]:  # Show first 5
                        report_lines.append(f"  - Line {match['line']}: {match['match']}")
                    if len(matches) > 5:
                        report_lines.append(f"  - ... and {len(matches) - 5} more")
                report_lines.append("")
            
            # AST usages
            if result["ast_matches"]["usages"]:
                report_lines.append("**Code Usages:**")
                for usage in result["ast_matches"]["usages"][:10]:  # Show first 10
                    func_context = f" in `{usage['function']}()`" if usage.get('function') else ""
                    report_lines.append(f"- {usage['type']}: `{usage.get('name', 'N/A')}` (line {usage['line']}){func_context}")
                if len(result["ast_matches"]["usages"]) > 10:
                    remaining = len(result["ast_matches"]["usages"]) - 10
                    report_lines.append(f"- ... and {remaining} more")
                report_lines.append("")
            
            report_lines.append("---")
            report_lines.append("")
    
    return "\n".join(report_lines)


def main():
    """Main function to run the assessment."""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    print("Scanning codebase for speaker_map usage...")
    
    all_results = []
    
    for source_dir in SOURCE_DIRS:
        source_path = project_root / source_dir
        if not source_path.exists():
            print(f"Warning: {source_path} does not exist")
            continue
        
        for py_file in source_path.rglob("*.py"):
            if should_exclude_file(py_file):
                continue
            
            print(f"Scanning: {py_file}")
            result = scan_file(py_file)
            all_results.append(result)
    
    # Generate report
    report = generate_report(all_results)
    
    # Save report
    report_path = project_root / "docs" / "development" / "SPEAKER_MAP_ASSESSMENT_REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\nAssessment complete!")
    print(f"Report saved to: {report_path}")
    print(f"\nSummary:")
    print(f"- Files scanned: {len(all_results)}")
    print(f"- Files with usage: {len([r for r in all_results if r.get('has_usage')])}")
    
    # Also save JSON for programmatic access
    json_path = project_root / "docs" / "development" / "SPEAKER_MAP_ASSESSMENT_DATA.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"Data saved to: {json_path}")


if __name__ == "__main__":
    main()
