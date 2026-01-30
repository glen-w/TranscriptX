#!/usr/bin/env python3
"""
TranscriptX Dependency Validation Script
Validates that all dependencies match expected versions and checks for conflicts.
"""

import sys
import pkg_resources
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


class DependencyValidator:
    """Validates project dependencies for consistency and security."""
    
    def __init__(self):
        self.critical_deps = {
            'numpy': '1.26.4',
            'torch': '2.2.2',
            'transformers': '4.54.0',
            'spacy': '3.7.5',
            'pandas': '2.3.0',
            'click': '8.2.1',
            'python-dotenv': '1.1.1',
            'structlog': '25.4.0',
            'tenacity': '9.1.2',
            'watchdog': '6.0.0',
            'humanize': '4.12.3',
            'alive-progress': '3.3.0',
            'prompt-toolkit': '3.0.51',
            'keyring': '25.6.0',
            'cryptography': '45.0.5',
            'pydantic': '2.9.2',
            'pydantic-settings': '2.10.1',
            'cerberus': '1.3.7',
            'marshmallow': '4.0.0',
            'jsonschema': '4.25.0',
            'networkx': '3.4.2'
        }
        
        self.conflict_groups = [
            ['numpy', 'pandas'],  # pandas depends on numpy
            ['torch', 'transformers'],  # transformers depends on torch
            ['spacy', 'thinc'],  # spacy depends on thinc
        ]
    
    def check_installed_versions(self) -> List[str]:
        """Check if installed versions match expected versions."""
        issues = []
        
        for package, expected_version in self.critical_deps.items():
            try:
                installed_version = pkg_resources.get_distribution(package).version
                if installed_version != expected_version:
                    issues.append(
                        f"Version mismatch: {package} expected {expected_version}, "
                        f"got {installed_version}"
                    )
            except pkg_resources.DistributionNotFound:
                issues.append(f"Missing package: {package}")
        
        return issues
    
    def check_conflicts(self) -> List[str]:
        """Check for potential dependency conflicts."""
        issues = []
        
        for group in self.conflict_groups:
            versions = {}
            for package in group:
                try:
                    versions[package] = pkg_resources.get_distribution(package).version
                except pkg_resources.DistributionNotFound:
                    continue
            
            if len(versions) > 1:
                # Check if versions are compatible
                if 'numpy' in versions and 'pandas' in versions:
                    numpy_ver = pkg_resources.parse_version(versions['numpy'])
                    pandas_ver = pkg_resources.parse_version(versions['pandas'])
                    
                    # pandas 2.3.0 requires numpy >= 1.24.0
                    if numpy_ver < pkg_resources.parse_version('1.24.0'):
                        issues.append(
                            f"Compatibility issue: pandas {versions['pandas']} "
                            f"requires numpy >= 1.24.0, but numpy {versions['numpy']} is installed"
                        )
        
        return issues
    
    def check_requirements_files(self) -> List[str]:
        """Check if requirements files are consistent."""
        issues = []
        
        # Check if requirements.txt exists
        req_file = Path('requirements.txt')
        if not req_file.exists():
            issues.append("requirements.txt not found")
            return issues
        
        # Check if requirements-lock.txt exists
        lock_file = Path('requirements-lock.txt')
        if not lock_file.exists():
            issues.append("requirements-lock.txt not found")
        
        # Parse requirements.txt and check for pinned versions
        with open(req_file, 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and '==' not in line:
                package = line.split('>=')[0].split('<=')[0].split('>')[0].split('<')[0].strip()
                if package in self.critical_deps:
                    issues.append(
                        f"Critical package {package} not pinned to exact version in requirements.txt"
                    )
        
        return issues
    
    def check_security_vulnerabilities(self) -> List[str]:
        """Check for known security vulnerabilities."""
        issues = []
        
        try:
            # Try to run safety scan (new command)
            result = subprocess.run(
                ['safety', 'scan', '-r', 'requirements.txt'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                issues.append(f"Security vulnerabilities found: {result.stdout}")
        
        except (subprocess.TimeoutExpired, FileNotFoundError):
            issues.append("safety not available for security check")
        
        return issues
    
    def validate_all(self) -> Tuple[bool, List[str]]:
        """Run all validation checks."""
        all_issues = []
        
        print("🔍 Running dependency validation...")
        
        # Check installed versions
        version_issues = self.check_installed_versions()
        if version_issues:
            print("❌ Version issues found:")
            for issue in version_issues:
                print(f"  - {issue}")
            all_issues.extend(version_issues)
        else:
            print("✅ All critical dependencies match expected versions")
        
        # Check conflicts
        conflict_issues = self.check_conflicts()
        if conflict_issues:
            print("❌ Conflict issues found:")
            for issue in conflict_issues:
                print(f"  - {issue}")
            all_issues.extend(conflict_issues)
        else:
            print("✅ No dependency conflicts detected")
        
        # Check requirements files
        req_issues = self.check_requirements_files()
        if req_issues:
            print("❌ Requirements file issues found:")
            for issue in req_issues:
                print(f"  - {issue}")
            all_issues.extend(req_issues)
        else:
            print("✅ Requirements files are consistent")
        
        # Check security
        security_issues = self.check_security_vulnerabilities()
        if security_issues:
            print("⚠️  Security issues found:")
            for issue in security_issues:
                print(f"  - {issue}")
            all_issues.extend(security_issues)
        else:
            print("✅ No security vulnerabilities detected")
        
        return len(all_issues) == 0, all_issues
    
    def generate_report(self) -> str:
        """Generate a comprehensive dependency report."""
        report = []
        report.append("# TranscriptX Dependency Report")
        report.append("")
        
        # Installed packages
        report.append("## Installed Critical Packages")
        for package, expected_version in self.critical_deps.items():
            try:
                installed_version = pkg_resources.get_distribution(package).version
                status = "✅" if installed_version == expected_version else "❌"
                report.append(f"- {status} {package}: {installed_version} (expected: {expected_version})")
            except pkg_resources.DistributionNotFound:
                report.append(f"- ❌ {package}: NOT INSTALLED (expected: {expected_version})")
        
        # Python environment
        report.append("")
        report.append("## Python Environment")
        report.append(f"- Python: {sys.version}")
        report.append(f"- pip: {pkg_resources.get_distribution('pip').version}")
        
        # File status
        report.append("")
        report.append("## Requirements Files")
        for filename in ['requirements.txt', 'requirements-lock.txt']:
            if Path(filename).exists():
                report.append(f"- ✅ {filename}: exists")
            else:
                report.append(f"- ❌ {filename}: missing")
        
        return "\n".join(report)


def main():
    """Main function for CLI usage."""
    validator = DependencyValidator()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--report':
        # Generate report
        report = validator.generate_report()
        print(report)
        return
    
    # Run validation
    success, issues = validator.validate_all()
    
    if success:
        print("\n🎉 All dependency validations passed!")
        sys.exit(0)
    else:
        print(f"\n❌ Found {len(issues)} issues:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)


if __name__ == '__main__':
    main() 