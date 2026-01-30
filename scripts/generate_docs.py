#!/usr/bin/env python3
"""
Documentation generator for TranscriptX.

This script generates documentation from code sources:
- CLI documentation from Typer help output
- Module catalog from ModuleRegistry

Generated files are placed in docs/generated/ and should not be manually edited.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any


class DocumentationGenerator:
    """Generate documentation from code sources."""
    
    def __init__(self):
        """Initialize the documentation generator."""
        self.project_root = Path(__file__).parent.parent
        self.docs_dir = self.project_root / "docs"
        self.generated_dir = self.docs_dir / "generated"
        
        # Ensure generated directory exists
        self.generated_dir.mkdir(parents=True, exist_ok=True)
    
    def strip_ansi_codes(self, text: str) -> str:
        """
        Remove ANSI color codes from text.
        
        Args:
            text: Text potentially containing ANSI codes
            
        Returns:
            Text with ANSI codes removed
        """
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def generate_cli_docs(self) -> None:
        """Generate CLI documentation from Typer help output."""
        print("Generating CLI documentation...")
        
        try:
            env = dict(os.environ)
            pythonpath = str(self.project_root / "src")
            if env.get("PYTHONPATH"):
                pythonpath = f"{pythonpath}{os.pathsep}{env['PYTHONPATH']}"
            env["PYTHONPATH"] = pythonpath
            env["TRANSCRIPTX_DOCS_MODE"] = "1"

            # Get main help
            result = subprocess.run(
                [sys.executable, "-m", "transcriptx.cli.main", "--help"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                env=env,
            )
            
            if result.returncode != 0:
                print(f"Warning: Failed to get CLI help: {result.stderr}")
                return
            
            main_help = self.strip_ansi_codes(result.stdout)
            
            # Get help for common subcommands
            subcommands = [
                "analyze",
                "transcribe",
                "identify-speakers",
                "process-wav",
                "batch-process",
                "database",
                "profiles",
                "transcript",
            ]
            
            subcommand_helps = {}
            for cmd in subcommands:
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "transcriptx.cli.main", cmd, "--help"],
                        capture_output=True,
                        text=True,
                        cwd=self.project_root,
                        env=env,
                        timeout=10
                    )
                    if result.returncode == 0:
                        subcommand_helps[cmd] = self.strip_ansi_codes(result.stdout)
                except (subprocess.TimeoutExpired, Exception) as e:
                    print(f"Warning: Could not get help for {cmd}: {e}")
            
            # Format as markdown
            markdown = self._format_cli_markdown(main_help, subcommand_helps)
            
            # Write to file
            output_file = self.generated_dir / "cli.md"
            output_file.write_text(markdown)
            print(f"✓ CLI documentation written to {output_file}")
            
        except Exception as e:
            print(f"Error generating CLI documentation: {e}")
            import traceback
            traceback.print_exc()
    
    def _format_cli_markdown(self, main_help: str, subcommand_helps: Dict[str, str]) -> str:
        """
        Format CLI help output as markdown.
        
        Args:
            main_help: Main command help text
            subcommand_helps: Dictionary of subcommand help texts
            
        Returns:
            Formatted markdown string
        """
        lines = [
            "# CLI Command Reference",
            "",
            "*This documentation is auto-generated from the CLI help output.*",
            "",
            "## Main Command",
            "",
            "```",
            main_help,
            "```",
            "",
        ]
        
        if subcommand_helps:
            lines.append("## Subcommands")
            lines.append("")
            
            for cmd, help_text in sorted(subcommand_helps.items()):
                lines.append(f"### {cmd}")
                lines.append("")
                lines.append("```")
                lines.append(help_text)
                lines.append("```")
                lines.append("")
        
        return "\n".join(lines)
    
    def generate_module_catalog(self) -> None:
        """Generate module catalog from ModuleRegistry."""
        print("Generating module catalog...")
        
        try:
            # Import ModuleRegistry
            sys.path.insert(0, str(self.project_root / "src"))
            from transcriptx.core.pipeline.module_registry import ModuleRegistry
            
            registry = ModuleRegistry()
            modules = registry.get_available_modules()
            
            # Collect module information
            module_data = []
            for module_name in sorted(modules):
                info = registry.get_module_info(module_name)
                if info:
                    module_data.append({
                        'name': info.name,
                        'description': info.description,
                        'category': info.category,
                        'dependencies': ', '.join(info.dependencies) if info.dependencies else 'None',
                        'determinism_tier': info.determinism_tier,
                    })
            
            # Format as markdown
            markdown = self._format_module_catalog_markdown(module_data)
            
            # Write to file
            output_file = self.generated_dir / "modules.md"
            output_file.write_text(markdown)
            print(f"✓ Module catalog written to {output_file}")
            
        except Exception as e:
            print(f"Error generating module catalog: {e}")
            import traceback
            traceback.print_exc()
    
    def _format_module_catalog_markdown(self, module_data: List[Dict[str, Any]]) -> str:
        """
        Format module data as markdown table.
        
        Args:
            module_data: List of module information dictionaries
            
        Returns:
            Formatted markdown string
        """
        lines = [
            "# Module Catalog",
            "",
            "*This catalog is auto-generated from the ModuleRegistry.*",
            "",
            "## Available Modules",
            "",
            "| Module | Description | Category | Dependencies | Determinism |",
            "|--------|-------------|----------|--------------|-------------|",
        ]
        
        for module in module_data:
            lines.append(
                f"| {module['name']} | {module['description']} | "
                f"{module['category']} | {module['dependencies']} | "
                f"{module['determinism_tier']} |"
            )
        
        lines.extend([
            "",
            "## Category Definitions",
            "",
            "- **light**: Fast, minimal computation (< 1 second per transcript)",
            "- **medium**: Moderate computation, may use ML models (1-10 seconds)",
            "- **heavy**: Intensive computation, large models (10+ seconds)",
            "",
            "## Determinism Tiers",
            "",
            "- **T0**: Fully deterministic - same input always produces same output",
            "- **T1**: Mostly deterministic - minor variations possible (e.g., floating point)",
            "- **T2**: Non-deterministic - output depends on model initialization or randomness",
            "",
        ])
        
        return "\n".join(lines)
    
    def run_all(self) -> None:
        """Run all documentation generators."""
        print("=" * 60)
        print("TranscriptX Documentation Generator")
        print("=" * 60)
        print()
        
        self.generate_cli_docs()
        print()
        self.generate_module_catalog()
        print()
        
        print("=" * 60)
        print("Documentation generation complete!")
        print(f"Generated files in: {self.generated_dir}")
        print("=" * 60)


def main():
    """Main entry point."""
    generator = DocumentationGenerator()
    generator.run_all()


if __name__ == "__main__":
    main()
