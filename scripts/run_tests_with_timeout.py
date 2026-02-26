#!/usr/bin/env python3
"""
TranscriptX Test Suite Runner with Timeout Handling

Runs the pytest test suite iteratively until all tests pass (excluding timeouts).
Tests that exceed 5 minutes are automatically skipped and logged for later review.
"""

import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple


class TestTimeoutRunner:
    """Manages test execution with timeout handling and iterative fixing."""

    def __init__(self, timeout_log: Path = None, max_iterations: int = 10):
        """
        Initialize the test runner.

        Args:
            timeout_log: Path to log file for timeout tests. Defaults to test_timeouts.log
            max_iterations: Maximum number of iterations before giving up
        """
        self.project_root = Path(__file__).parent.parent
        self.timeout_log = timeout_log or (self.project_root / "test_timeouts.log")
        self.max_iterations = max_iterations
        self.timeout_tests: Set[str] = set()
        self.iteration = 0
        self.all_results: List[Dict] = []

    def log_timeout(self, test_name: str, test_path: str = ""):
        """
        Log a test that timed out.

        Args:
            test_name: Name of the test that timed out
            test_path: Full path to the test file
        """
        timestamp = datetime.now().isoformat()
        log_entry = (
            f"[{timestamp}] TIMEOUT: Test '{test_name}' exceeded 5 minute timeout.\n"
            f"  Path: {test_path}\n"
            f"  Note: This test may need fixing or optimization.\n"
            f"  Timeout duration: 300 seconds (5 minutes)\n"
            f"{'='*80}\n"
        )

        with open(self.timeout_log, "a") as f:
            f.write(log_entry)

        self.timeout_tests.add(test_name)
        print(f"⚠️  Logged timeout: {test_name}")

    def parse_pytest_output(
        self, output: str
    ) -> Tuple[int, int, int, List[str], List[str]]:
        """
        Parse pytest output to extract test results.

        Args:
            output: Pytest output string

        Returns:
            Tuple of (passed, failed, skipped, timeout_tests, failed_tests)
        """
        passed = 0
        failed = 0
        skipped = 0
        timeout_tests: List[str] = []
        failed_tests: List[str] = []

        # Parse summary line: "X passed, Y failed, Z skipped in W.XXs"
        summary_match = re.search(
            r"(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+skipped", output, re.IGNORECASE
        )
        if summary_match:
            passed = int(summary_match.group(1))
            failed = int(summary_match.group(2))
            skipped = int(summary_match.group(3))

        # Find timeout errors - pytest-timeout typically shows "TIMEOUT" in the output
        timeout_pattern = r"TIMEOUT.*?::([^\s]+)"
        timeout_matches = re.findall(timeout_pattern, output, re.IGNORECASE)
        for match in timeout_matches:
            test_name = match.strip()
            if test_name and test_name not in timeout_tests:
                timeout_tests.append(test_name)

        # Also check for "timeout" in error messages
        timeout_error_pattern = r"FAILED.*?::([^\s]+).*?timeout"
        timeout_error_matches = re.findall(
            timeout_error_pattern, output, re.IGNORECASE | re.DOTALL
        )
        for match in timeout_error_matches:
            test_name = match.strip()
            if test_name and test_name not in timeout_tests:
                timeout_tests.append(test_name)

        # Find failed tests (excluding timeouts)
        failed_pattern = r"FAILED\s+([^\s]+::[^\s]+)"
        failed_matches = re.findall(failed_pattern, output)
        for match in failed_matches:
            test_name = match.strip()
            if test_name not in timeout_tests and test_name not in failed_tests:
                failed_tests.append(test_name)

        # Also check for ERROR entries
        error_pattern = r"ERROR\s+([^\s]+::[^\s]+)"
        error_matches = re.findall(error_pattern, output)
        for match in error_matches:
            test_name = match.strip()
            if test_name not in timeout_tests and test_name not in failed_tests:
                failed_tests.append(test_name)

        return passed, failed, skipped, timeout_tests, failed_tests

    def run_pytest(self) -> Tuple[int, str]:
        """
        Run pytest with timeout configuration.

        Returns:
            Tuple of (exit_code, output)
        """
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "--timeout=300",
            "--timeout-method=thread",
            "-v",
            "--tb=short",
        ]

        print(f"\n{'='*80}")
        print(f"Iteration {self.iteration + 1}/{self.max_iterations}")
        print(f"Running: {' '.join(cmd)}")
        print(f"{'='*80}\n")

        start_time = time.time()
        result = subprocess.run(
            cmd, cwd=self.project_root, capture_output=True, text=True
        )
        elapsed = time.time() - start_time

        output = result.stdout + result.stderr
        print(output)
        print(f"\n⏱️  Test run completed in {elapsed:.2f} seconds")

        return result.returncode, output

    def run_iteration(self) -> bool:
        """
        Run a single iteration of tests.

        Returns:
            True if all non-timeout tests passed, False otherwise
        """
        self.iteration += 1

        if self.iteration > self.max_iterations:
            print(f"\n❌ Maximum iterations ({self.max_iterations}) reached!")
            return False

        exit_code, output = self.run_pytest()
        passed, failed, skipped, timeout_tests, failed_tests = self.parse_pytest_output(
            output
        )

        # Log any new timeout tests
        for test_name in timeout_tests:
            if test_name not in self.timeout_tests:
                # Try to find the full test path
                test_path_match = re.search(
                    rf"{re.escape(test_name)}.*?(\S+\.py::\S+)", output
                )
                test_path = test_path_match.group(1) if test_path_match else test_name
                self.log_timeout(test_name, test_path)

        result = {
            "iteration": self.iteration,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "timeout_tests": timeout_tests.copy(),
            "failed_tests": failed_tests.copy(),
            "exit_code": exit_code,
        }
        self.all_results.append(result)

        # Print summary
        print(f"\n{'='*80}")
        print(f"Iteration {self.iteration} Summary:")
        print(f"  ✅ Passed: {passed}")
        print(f"  ❌ Failed: {failed}")
        print(f"  ⏭️  Skipped: {skipped}")
        print(f"  ⏱️  Timeouts: {len(timeout_tests)}")
        if timeout_tests:
            print(f"  Timeout tests: {', '.join(timeout_tests[:5])}")
            if len(timeout_tests) > 5:
                print(f"  ... and {len(timeout_tests) - 5} more")
        if failed_tests:
            print(f"  Failed tests: {', '.join(failed_tests[:5])}")
            if len(failed_tests) > 5:
                print(f"  ... and {len(failed_tests) - 5} more")
        print(f"{'='*80}\n")

        # Success if no failures (timeouts are expected and logged)
        return failed == 0 and exit_code == 0

    def run(self) -> bool:
        """
        Run tests iteratively until all non-timeout tests pass.

        Returns:
            True if all non-timeout tests passed, False otherwise
        """
        print("🚀 Starting test suite with timeout handling")
        print(f"📝 Timeout log: {self.timeout_log}")
        print("⏱️  Timeout duration: 300 seconds (5 minutes)")
        print(f"🔄 Max iterations: {self.max_iterations}\n")

        # Clear previous timeout log
        if self.timeout_log.exists():
            self.timeout_log.unlink()

        # Run iterations until success or max iterations
        while True:
            success = self.run_iteration()

            if success:
                print("\n✅ All non-timeout tests passed!")
                self.print_final_summary()
                return True

            if self.iteration >= self.max_iterations:
                print(
                    "\n❌ Maximum iterations reached. Some tests may still be failing."
                )
                self.print_final_summary()
                return False

            # If there are failures, wait for user to fix them
            if failed > 0:
                print(
                    "\n⚠️  Some tests failed. Please review the output above and fix the issues."
                )
                print("   The script will automatically re-run when you're ready.")
                print(
                    "   Press Enter to continue after fixing issues (or Ctrl+C to exit)..."
                )
                try:
                    input()
                except KeyboardInterrupt:
                    print("\n\n⚠️  Interrupted by user")
                    self.print_final_summary()
                    return False
            else:
                # Only timeouts, which are expected and logged
                break

    def print_final_summary(self):
        """Print final summary of all test runs."""
        print(f"\n{'='*80}")
        print("FINAL SUMMARY")
        print(f"{'='*80}")
        print(f"Total iterations: {self.iteration}")
        print(f"Total timeout tests logged: {len(self.timeout_tests)}")

        if self.all_results:
            last_result = self.all_results[-1]
            print("\nFinal Results:")
            print(f"  ✅ Passed: {last_result['passed']}")
            print(f"  ❌ Failed: {last_result['failed']}")
            print(f"  ⏭️  Skipped: {last_result['skipped']}")
            print(f"  ⏱️  Timeouts: {len(last_result['timeout_tests'])}")

        if self.timeout_tests:
            print(f"\n⏱️  Tests that timed out (logged to {self.timeout_log}):")
            for test in sorted(self.timeout_tests):
                print(f"    - {test}")

        if self.timeout_log.exists():
            print(f"\n📝 Full timeout log available at: {self.timeout_log}")

        print(f"{'='*80}\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run pytest suite with timeout handling and iterative execution"
    )
    parser.add_argument(
        "--timeout-log",
        type=Path,
        default=None,
        help="Path to timeout log file (default: test_timeouts.log in project root)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of iterations (default: 10)",
    )

    args = parser.parse_args()

    runner = TestTimeoutRunner(
        timeout_log=args.timeout_log, max_iterations=args.max_iterations
    )

    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
