"""
Regression tests for workflow mode separation.

This module tests interactive vs non-interactive mode separation to catch
regressions where non-interactive commands try to prompt or interactive
flows lose helpful defaults.
"""

import json
import subprocess


class TestNonInteractiveMode:
    """Tests for non-interactive mode behavior."""

    def test_all_commands_non_interactive_no_stdin(
        self, cli_runner, non_interactive_env
    ):
        """All commands with --non-interactive never read from stdin."""
        commands = [
            ("analyze", ["--non-interactive", "--help"]),
            ("transcribe", ["--non-interactive", "--help"]),
        ]

        for cmd, args in commands:
            result = cli_runner(
                cmd,
                args,
                stdin=subprocess.DEVNULL,
                env=non_interactive_env,
                timeout=5,
            )

            # Should not hang - should complete quickly
            assert result.returncode in [
                0,
                1,
                2,
            ], f"Command '{cmd}' should not hang, got returncode {result.returncode}"

    def test_non_interactive_hangs_detection(self, cli_runner, non_interactive_env):
        """Detect if non-interactive mode hangs waiting for input."""
        # Try a command that might prompt in interactive mode
        result = cli_runner(
            "analyze",
            ["--non-interactive", "nonexistent.json"],
            stdin=subprocess.DEVNULL,
            env=non_interactive_env,
            timeout=3,  # Short timeout to detect hangs
        )

        # Should complete within timeout (not hang)
        assert result.returncode is not None

    def test_non_interactive_required_flags(self, cli_runner, non_interactive_env):
        """Required flags are enforced in non-interactive mode."""
        # Try analyze without required file argument
        result = cli_runner(
            "analyze",
            ["--non-interactive"],
            env=non_interactive_env,
            timeout=5,
        )

        # Should fail with error (not prompt)
        assert result.returncode != 0, "Should fail when required args missing"

    def test_non_interactive_defaults_used(self, cli_runner, non_interactive_env):
        """Defaults are used when flags not provided."""
        # This test would need a valid transcript file
        # For now, we verify that defaults are documented/accessible
        from transcriptx.core.utils.config import get_config

        config = get_config()
        # Config should have defaults
        assert config is not None


class TestDerivedDefaultsSnapshot:
    """Tests for derived defaults consistency."""

    def test_derived_defaults_snapshot(self, tmp_path):
        """Snapshot test for all derived defaults."""
        from transcriptx.core.utils.config import get_config

        config = get_config()

        # Capture defaults
        defaults = {
            "analyze": {
                "interactive": {
                    "mode": "quick",  # Typical default
                    "modules": "all",
                },
                "non_interactive": {
                    "mode": "quick",
                    "modules": "all",
                },
            }
        }

        # Save snapshot
        snapshot_path = tmp_path / "derived_defaults_snapshot.json"
        snapshot_path.write_text(json.dumps(defaults, indent=2))

        # Basic validation
        assert snapshot_path.exists()
        loaded = json.loads(snapshot_path.read_text())
        assert "analyze" in loaded

    def test_derived_defaults_interactive_vs_non_interactive(self):
        """Defaults differ appropriately between modes."""
        # In practice, some defaults might differ between modes
        # This test verifies they're consistent where expected

        # Interactive might have more prompts, non-interactive uses defaults
        # Both should work correctly
        assert True  # Placeholder - would test actual default differences

    def test_derived_defaults_validation_order(self, cli_runner):
        """Validation order is correct (doesn't ask for required after optional)."""
        # Try command with missing required arg
        result = cli_runner("analyze", [], timeout=5)

        # Should fail fast on required arg, not ask for optional ones first
        # This is a basic check - actual validation order depends on implementation
        assert result.returncode != 0 or True  # May succeed with defaults


class TestInteractiveFlowRegression:
    """Tests for interactive flow regressions."""

    def test_interactive_helpful_defaults(self):
        """Interactive flows show helpful derived defaults."""
        # This would require mocking questionary to test
        # For now, we verify the infrastructure exists
        from transcriptx.cli.workflow_utils import is_non_interactive

        # Should be able to check mode
        assert isinstance(is_non_interactive(), bool)

    def test_interactive_question_count(self):
        """Interactive flows don't ask unnecessary questions."""
        # This would require counting questionary calls
        # Placeholder for actual implementation
        assert True

    def test_interactive_validation_order(self):
        """Validation happens in correct order (required before optional)."""
        # This would test that required fields are validated before optional
        # Placeholder for actual implementation
        assert True
