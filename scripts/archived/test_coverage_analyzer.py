#!/usr/bin/env python3
"""
Test Coverage Analyzer for TranscriptX

This script analyzes the current test coverage and identifies specific gaps
that need to be addressed to improve the testing infrastructure.
"""

import ast
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List


class TestCoverageAnalyzer:
    """Analyzes test coverage and identifies gaps."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_dir = project_root / "src"
        self.tests_dir = project_root / "tests"
        self.results = {}

    def analyze_coverage(self):
        """Run comprehensive coverage analysis."""
        print("🔍 TranscriptX Test Coverage Analysis")
        print("=" * 50)

        # Analyze source code structure
        source_modules = self.analyze_source_structure()

        # Analyze test structure
        test_modules = self.analyze_test_structure()

        # Identify coverage gaps
        coverage_gaps = self.identify_coverage_gaps(source_modules, test_modules)

        # Generate recommendations
        recommendations = self.generate_recommendations(coverage_gaps)

        # Save results
        self.save_analysis_results(
            {
                "source_modules": source_modules,
                "test_modules": test_modules,
                "coverage_gaps": coverage_gaps,
                "recommendations": recommendations,
            }
        )

        # Print summary
        self.print_analysis_summary()

    def analyze_source_structure(self) -> Dict:
        """Analyze the source code structure."""
        print("\n📊 Source Code Analysis")
        print("-" * 30)

        source_modules = {
            "total_files": 0,
            "total_lines": 0,
            "modules": {},
            "functions": {},
            "classes": {},
            "imports": set(),
        }

        for py_file in self.src_dir.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue

            source_modules["total_files"] += 1

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    source_modules["total_lines"] += len(content.splitlines())

                # Parse AST for detailed analysis
                tree = ast.parse(content)
                module_info = self.analyze_ast_tree(tree, py_file)

                relative_path = py_file.relative_to(self.src_dir)
                source_modules["modules"][str(relative_path)] = module_info

                # Collect functions and classes
                for func in module_info["functions"]:
                    source_modules["functions"][f"{relative_path}:{func}"] = {
                        "module": str(relative_path),
                        "name": func,
                    }

                for cls in module_info["classes"]:
                    source_modules["classes"][f"{relative_path}:{cls}"] = {
                        "module": str(relative_path),
                        "name": cls,
                    }

            except Exception as e:
                print(f"⚠️  Error analyzing {py_file}: {e}")

        print(f"✅ Total source files: {source_modules['total_files']}")
        print(f"✅ Total source lines: {source_modules['total_lines']}")
        print(f"✅ Total functions: {len(source_modules['functions'])}")
        print(f"✅ Total classes: {len(source_modules['classes'])}")

        return source_modules

    def analyze_ast_tree(self, tree: ast.AST, file_path: Path) -> Dict:
        """Analyze an AST tree for functions, classes, and imports."""
        module_info = {"functions": [], "classes": [], "imports": [], "lines": 0}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                module_info["functions"].append(node.name)
            elif isinstance(node, ast.ClassDef):
                module_info["classes"].append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module_info["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module_info["imports"].append(
                    f"{node.module}.{', '.join(n.name for n in node.names)}"
                )

        return module_info

    def analyze_test_structure(self) -> Dict:
        """Analyze the test structure."""
        print("\n🧪 Test Structure Analysis")
        print("-" * 30)

        test_modules = {
            "total_files": 0,
            "total_tests": 0,
            "test_categories": defaultdict(int),
            "tested_modules": set(),
            "test_functions": {},
            "test_classes": {},
        }

        for py_file in self.tests_dir.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue

            test_modules["total_files"] += 1

            # Determine test category
            relative_path = py_file.relative_to(self.tests_dir)
            category = relative_path.parts[0] if relative_path.parts else "root"
            test_modules["test_categories"][category] += 1

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Count test functions
                test_count = content.count("def test_")
                test_modules["total_tests"] += test_count

                # Parse AST for detailed analysis
                tree = ast.parse(content)
                test_info = self.analyze_test_ast_tree(tree, py_file)

                # Track tested modules
                for module in test_info["tested_modules"]:
                    test_modules["tested_modules"].add(module)

                # Track test functions and classes
                for func in test_info["test_functions"]:
                    test_modules["test_functions"][f"{relative_path}:{func}"] = {
                        "file": str(relative_path),
                        "name": func,
                        "category": category,
                    }

                for cls in test_info["test_classes"]:
                    test_modules["test_classes"][f"{relative_path}:{cls}"] = {
                        "file": str(relative_path),
                        "name": cls,
                        "category": category,
                    }

            except Exception as e:
                print(f"⚠️  Error analyzing test file {py_file}: {e}")

        print(f"✅ Total test files: {test_modules['total_files']}")
        print(f"✅ Total test functions: {test_modules['total_tests']}")
        print(f"✅ Test categories: {dict(test_modules['test_categories'])}")
        print(f"✅ Tested modules: {len(test_modules['tested_modules'])}")

        return test_modules

    def analyze_test_ast_tree(self, tree: ast.AST, file_path: Path) -> Dict:
        """Analyze test AST tree for test functions and tested modules."""
        test_info = {"test_functions": [], "test_classes": [], "tested_modules": set()}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                test_info["test_functions"].append(node.name)
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                test_info["test_classes"].append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "transcriptx" in alias.name:
                        test_info["tested_modules"].add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "transcriptx" in node.module:
                    test_info["tested_modules"].add(node.module)

        return test_info

    def identify_coverage_gaps(self, source_modules: Dict, test_modules: Dict) -> Dict:
        """Identify specific coverage gaps."""
        print("\n🔍 Coverage Gap Analysis")
        print("-" * 30)

        gaps = {
            "untested_modules": [],
            "untested_functions": [],
            "untested_classes": [],
            "missing_test_categories": [],
            "coverage_metrics": {},
        }

        # Find untested modules
        tested_modules = test_modules["tested_modules"]
        for module_path in source_modules["modules"]:
            module_name = (
                f"transcriptx.{module_path.replace('/', '.').replace('.py', '')}"
            )
            if module_name not in tested_modules:
                gaps["untested_modules"].append(module_path)

        # Find untested functions
        for func_key, func_info in source_modules["functions"].items():
            module_name = func_info["module"].replace("/", ".").replace(".py", "")
            if not any(module_name in tested for tested in tested_modules):
                gaps["untested_functions"].append(func_key)

        # Find untested classes
        for class_key, class_info in source_modules["classes"].items():
            module_name = class_info["module"].replace("/", ".").replace(".py", "")
            if not any(module_name in tested for tested in tested_modules):
                gaps["untested_classes"].append(class_key)

        # Calculate coverage metrics
        total_modules = len(source_modules["modules"])
        tested_modules_count = len(tested_modules)
        gaps["coverage_metrics"] = {
            "module_coverage": (
                (tested_modules_count / total_modules) * 100 if total_modules > 0 else 0
            ),
            "function_coverage": (
                (
                    (len(source_modules["functions"]) - len(gaps["untested_functions"]))
                    / len(source_modules["functions"])
                )
                * 100
                if source_modules["functions"]
                else 0
            ),
            "class_coverage": (
                (
                    (len(source_modules["classes"]) - len(gaps["untested_classes"]))
                    / len(source_modules["classes"])
                )
                * 100
                if source_modules["classes"]
                else 0
            ),
        }

        print(f"⚠️  Untested modules: {len(gaps['untested_modules'])}")
        print(f"⚠️  Untested functions: {len(gaps['untested_functions'])}")
        print(f"⚠️  Untested classes: {len(gaps['untested_classes'])}")
        print(f"📊 Module coverage: {gaps['coverage_metrics']['module_coverage']:.1f}%")
        print(
            f"📊 Function coverage: {gaps['coverage_metrics']['function_coverage']:.1f}%"
        )
        print(f"📊 Class coverage: {gaps['coverage_metrics']['class_coverage']:.1f}%")

        return gaps

    def generate_recommendations(self, gaps: Dict) -> List[Dict]:
        """Generate specific recommendations for improving coverage."""
        print("\n💡 Recommendations")
        print("-" * 30)

        recommendations = []

        # High priority recommendations
        if gaps["untested_modules"]:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "category": "Module Coverage",
                    "title": "Add tests for untested modules",
                    "description": f"Create test files for {len(gaps['untested_modules'])} untested modules",
                    "modules": gaps["untested_modules"][:10],  # Show first 10
                    "effort": "Medium",
                    "impact": "High",
                }
            )

        if gaps["untested_functions"]:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "category": "Function Coverage",
                    "title": "Add unit tests for untested functions",
                    "description": f"Create unit tests for {len(gaps['untested_functions'])} untested functions",
                    "functions": gaps["untested_functions"][:10],  # Show first 10
                    "effort": "Medium",
                    "impact": "High",
                }
            )

        # Medium priority recommendations
        if gaps["coverage_metrics"]["module_coverage"] < 50:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": "Coverage Improvement",
                    "title": "Improve overall module coverage",
                    "description": f"Current module coverage is {gaps['coverage_metrics']['module_coverage']:.1f}%. Target: 80%",
                    "effort": "High",
                    "impact": "Medium",
                }
            )

        # Low priority recommendations
        recommendations.append(
            {
                "priority": "LOW",
                "category": "Test Quality",
                "title": "Add integration tests",
                "description": "Create more end-to-end integration tests",
                "effort": "High",
                "impact": "Medium",
            }
        )

        recommendations.append(
            {
                "priority": "LOW",
                "category": "Test Infrastructure",
                "title": "Set up CI/CD pipeline",
                "description": "Automate test execution and coverage reporting",
                "effort": "Medium",
                "impact": "Low",
            }
        )

        for rec in recommendations:
            print(f"🔸 {rec['priority']}: {rec['title']}")
            print(f"   {rec['description']}")

        return recommendations

    def save_analysis_results(self, results: Dict):
        """Save analysis results to JSON file."""
        output_file = self.project_root / "test_coverage_analysis.json"

        # Convert sets to lists for JSON serialization
        serializable_results = {}
        for key, value in results.items():
            if isinstance(value, dict):
                serializable_results[key] = {}
                for k, v in value.items():
                    if isinstance(v, set):
                        serializable_results[key][k] = list(v)
                    else:
                        serializable_results[key][k] = v
            else:
                serializable_results[key] = value

        with open(output_file, "w") as f:
            json.dump(serializable_results, f, indent=2)

        print(f"\n💾 Analysis results saved to: {output_file}")

    def print_analysis_summary(self):
        """Print a summary of the analysis."""
        print("\n📋 Analysis Summary")
        print("=" * 50)
        print("✅ Analysis completed successfully")
        print("📊 Detailed results saved to test_coverage_analysis.json")
        print("💡 Review recommendations above for next steps")
        print("🎯 Focus on HIGH priority items first")


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    analyzer = TestCoverageAnalyzer(project_root)
    analyzer.analyze_coverage()


if __name__ == "__main__":
    main()
