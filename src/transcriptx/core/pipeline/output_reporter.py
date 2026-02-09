"""
Output reporter for TranscriptX pipeline.

This module handles output summary generation and display,
providing centralized reporting functionality.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console

from transcriptx.core.pipeline.module_registry import get_module_info
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.output_validation import validate_module_outputs
from transcriptx.core.utils.path_utils import get_transcript_dir

logger = get_logger()
console = Console()


def _get_module_output_dir(basename_dir: Path, module_name: str) -> Path:
    """
    Resolve the actual output directory for a module.

    - transcript_output writes to run root (transcripts/ subdir); use basename_dir.
    - simplified_transcript writes to basename_dir/transcripts/; use that.
    - Modules with output_namespace and output_version (e.g. voice_charts_core)
      write to basename_dir / namespace / version.
    - Others use basename_dir / module_name.
    """
    if module_name in ("transcript_output", "simplified_transcript"):
        return basename_dir / "transcripts"
    info = get_module_info(module_name)
    if info and info.output_namespace and info.output_version:
        return basename_dir / info.output_namespace / info.output_version
    return basename_dir / module_name


class OutputReporter:
    """
    Service for handling output reporting and display.

    This class provides centralized logic for:
    - Generating comprehensive output summaries
    - Displaying results to users
    - Validating module outputs
    """

    def __init__(self):
        """Initialize the output reporter."""
        self.logger = get_logger()
        self.console = console

    def generate_comprehensive_output_summary(
        self,
        transcript_path: str,
        selected_modules: List[str],
        modules_run: List[str],
        errors: List[str],
        skipped_modules: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive summary of all outputs generated during analysis.

        Args:
            transcript_path: Path to the transcript file that was processed
            selected_modules: List of modules that were requested to run
            modules_run: List of modules that were successfully executed
            errors: List of error messages from failed modules

        Returns:
            Dictionary containing comprehensive output summary
        """
        self.logger.debug(f"Generating output summary for: {transcript_path}")

        base_name = os.path.splitext(os.path.basename(transcript_path))[0]
        transcript_dir = get_transcript_dir(transcript_path)
        basename_dir = Path(transcript_dir)

        modules_run_set = {m.lower() for m in modules_run}
        def _ran(mod: str) -> bool:
            return mod in modules_run or mod.lower() in modules_run_set

        skipped_by_module = {
            entry["module"]: entry for entry in (skipped_modules or [])
        }
        modules_failed = [
            mod
            for mod in selected_modules
            if not _ran(mod) and mod not in skipped_by_module
        ]

        summary = {
            "transcript_info": {
                "file_path": transcript_path,
                "base_name": base_name,
                "output_directory": transcript_dir,
            },
            "analysis_summary": {
                "modules_requested": selected_modules,
                "modules_successfully_run": modules_run,
                "modules_failed": modules_failed,
                "total_modules_requested": len(selected_modules),
                "total_modules_successful": len(modules_run),
                "total_modules_failed": len(modules_failed),
                "errors": errors,
            },
            "outputs": {
                "successful_modules": {},
                "skipped_modules": {},
                "failed_modules": {},
                "additional_files": [],
            },
            "validation": {},
        }

        # Check if output directory exists
        if not basename_dir.exists():
            summary["outputs"][
                "error"
            ] = f"Output directory does not exist: {transcript_dir}"
            return summary

        # Validate module outputs
        validation_results = validate_module_outputs(basename_dir, selected_modules)
        summary["validation"] = validation_results

        # Scan for all outputs (use _ran for consistent module-name comparison)
        for module_name in selected_modules:
            module_dir = _get_module_output_dir(basename_dir, module_name)
            in_run = _ran(module_name)

            if in_run and module_dir.exists():
                # Module was successfully run
                module_outputs = {
                    "directory": str(module_dir),
                    "files": [],
                    "subdirectories": [],
                    "validation": validation_results.get(module_name, (False, [])),
                }

                # Scan for files and subdirectories
                for item in module_dir.rglob("*"):
                    if item.is_file():
                        relative_path = item.relative_to(module_dir)
                        file_info = {
                            "path": str(relative_path),
                            "full_path": str(item),
                            "size_bytes": item.stat().st_size,
                            "extension": item.suffix,
                        }
                        module_outputs["files"].append(file_info)
                    elif item.is_dir() and item != module_dir:
                        relative_path = item.relative_to(module_dir)
                        module_outputs["subdirectories"].append(str(relative_path))

                summary["outputs"]["successful_modules"][module_name] = module_outputs
            elif module_name in skipped_by_module:
                summary["outputs"]["skipped_modules"][module_name] = {
                    "directory": str(module_dir),
                    "exists": module_dir.exists(),
                    "reason": skipped_by_module[module_name].get(
                        "reason", "Skipped"
                    ),
                }
            else:
                # Module failed or wasn't run
                summary["outputs"]["failed_modules"][module_name] = {
                    "directory": str(module_dir),
                    "exists": module_dir.exists(),
                    "error": next(
                        (err for err in errors if module_name in err),
                        "Module not executed",
                    ),
                }

        # Look for additional files in the main transcript directory
        for item in basename_dir.iterdir():
            if item.is_file() and item.name not in selected_modules:
                file_info = {
                    "name": item.name,
                    "path": str(item),
                    "size_bytes": item.stat().st_size,
                    "extension": item.suffix,
                }
                summary["outputs"]["additional_files"].append(file_info)

        return summary

    def display_output_summary_to_user(self, summary: Dict[str, Any]) -> None:
        """
        Display a user-friendly summary of all outputs to the console.

        Args:
            summary: Output summary dictionary from generate_comprehensive_output_summary
        """
        self.console.print("\n" + "=" * 80)
        self.console.print("📊 COMPREHENSIVE ANALYSIS OUTPUT SUMMARY")
        self.console.print("=" * 80)

        # Basic info
        transcript_info = summary.get("transcript_info", {})
        analysis_summary = summary.get("analysis_summary", {})

        base_name = transcript_info.get("base_name", "Unknown")
        output_directory = transcript_info.get("output_directory", "Unknown")
        total_success = analysis_summary.get("total_modules_successful", 0)
        total_requested = analysis_summary.get(
            "total_modules_requested",
            total_success + analysis_summary.get("total_modules_failed", 0),
        )
        errors = analysis_summary.get("errors", [])

        self.console.print(f"\n Transcript: {base_name}")
        self.console.print(
            f"📂 Output Directory: {output_directory}"
        )
        self.console.print(
            f"🔄 Analysis Status: {total_success}/{total_requested} modules completed"
        )

        if errors:
            self.console.print(f"⚠️  Errors: {len(errors)}")

        outputs = summary.get("outputs", {})

        # Successful modules
        successful_modules = outputs.get("successful_modules", {})
        if successful_modules:
            self.console.print(
                f"\n✅ SUCCESSFULLY COMPLETED MODULES ({len(successful_modules)}):"
            )
            self.console.print("-" * 50)

            for module_name, module_data in successful_modules.items():
                is_valid, validation_warnings = module_data["validation"]
                status_icon = "✅" if not validation_warnings else "⚠️"
                self.console.print(f"\n{status_icon} {module_name.upper()}")
                self.console.print(f"   📁 Directory: {module_data['directory']}")
                self.console.print(f"   📄 Files: {len(module_data['files'])}")
                self.console.print(
                    f"   📂 Subdirectories: {len(module_data['subdirectories'])}"
                )

                # Show key files
                key_files = [
                    f
                    for f in module_data["files"]
                    if any(
                        ext in f["extension"]
                        for ext in [".json", ".png", ".html", ".txt", ".csv"]
                    )
                ]
                if key_files:
                    self.console.print("   📋 Key outputs:")
                    for file_info in key_files[:5]:  # Show first 5 key files
                        size_kb = file_info["size_bytes"] / 1024
                        self.console.print(
                            f"      • {file_info['path']} ({size_kb:.1f} KB)"
                        )
                    if len(key_files) > 5:
                        self.console.print(
                            f"      • ... and {len(key_files) - 5} more files"
                        )

                if validation_warnings:
                    self.console.print(
                        f"   ⚠️  Validation warnings: {', '.join(validation_warnings[:3])}"
                    )
                    if len(validation_warnings) > 3:
                        self.console.print(
                            f"      ... and {len(validation_warnings) - 3} more warnings"
                        )

        # Skipped modules
        skipped_modules = outputs.get("skipped_modules", {})
        if skipped_modules:
            self.console.print(
                f"\n⏭️  SKIPPED MODULES ({len(skipped_modules)}):"
            )
            self.console.print("-" * 30)

            for module_name, module_data in skipped_modules.items():
                self.console.print(f"\n⏭️  {module_name.upper()}")
                self.console.print(f"   📁 Directory: {module_data['directory']}")
                self.console.print(f"   ⚠️  Reason: {module_data['reason']}")

        # Failed modules
        failed_modules = outputs.get("failed_modules", {})
        if failed_modules:
            self.console.print(f"\n❌ FAILED MODULES ({len(failed_modules)}):")
            self.console.print("-" * 30)

            for module_name, module_data in failed_modules.items():
                self.console.print(f"\n❌ {module_name.upper()}")
                self.console.print(f"   📁 Directory: {module_data['directory']}")
                self.console.print(f"   ❌ Error: {module_data['error']}")

        # Additional files
        additional_files = outputs.get("additional_files", [])
        if additional_files:
            self.console.print(f"\n📄 ADDITIONAL FILES ({len(additional_files)}):")
            self.console.print("-" * 30)

            for file_info in additional_files:
                size_kb = file_info["size_bytes"] / 1024
                self.console.print(f"   • {file_info['name']} ({size_kb:.1f} KB)")

        # Summary statistics
        total_files = sum(
            len(module_data["files"]) for module_data in successful_modules.values()
        )
        total_size_mb = sum(
            sum(file_info["size_bytes"] for file_info in module_data["files"])
            for module_data in successful_modules.values()
        ) / (1024 * 1024)

        self.console.print("\n📈 SUMMARY STATISTICS:")
        self.console.print("-" * 25)
        self.console.print(f"   • Total files generated: {total_files}")
        self.console.print(f"   • Total output size: {total_size_mb:.1f} MB")
        self.console.print(f"   • Successful modules: {len(successful_modules)}")
        self.console.print(f"   • Failed modules: {len(failed_modules)}")

        # Recommendations
        if failed_modules:
            self.console.print("\n💡 RECOMMENDATIONS:")
            self.console.print("-" * 20)
            self.console.print("   • Check error messages above for failed modules")
            self.console.print("   • Consider re-running failed modules individually")
            self.console.print("   • Verify input data quality for failed modules")

        self.console.print("\n" + "=" * 80)


# Global output reporter instance
_output_reporter = OutputReporter()


def generate_comprehensive_output_summary(
    transcript_path: str,
    selected_modules: List[str],
    modules_run: List[str],
    errors: List[str],
    skipped_modules: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Generate a comprehensive summary of all outputs generated during analysis."""
    return _output_reporter.generate_comprehensive_output_summary(
        transcript_path, selected_modules, modules_run, errors, skipped_modules
    )


def display_output_summary_to_user(summary: Dict[str, Any]) -> None:
    """Display a user-friendly summary of all outputs to the console."""
    _output_reporter.display_output_summary_to_user(summary)
