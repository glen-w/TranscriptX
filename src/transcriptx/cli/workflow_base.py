"""
Base classes for interactive and non-interactive workflows.

This module provides abstract base classes that separate interactive
and non-interactive workflow logic, making workflows easier to test
and maintain.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    status: str  # "success", "cancelled", "failed", "requires_interaction"
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

    @property
    def is_success(self) -> bool:
        """Whether the workflow completed successfully."""
        return self.status == "success"

    @property
    def is_cancelled(self) -> bool:
        """Whether the workflow was cancelled by the user."""
        return self.status == "cancelled"

    @property
    def requires_interaction(self) -> bool:
        """Whether the workflow requires user interaction."""
        return self.status == "requires_interaction"


class InteractiveWorkflow(ABC):
    """
    Abstract base class for interactive workflows.

    Interactive workflows use questionary for user prompts and are
    designed for human interaction. They should not be used in
    automated scripts or tests.
    """

    @abstractmethod
    def run(self) -> None:
        """
        Run the interactive workflow.

        This method handles all user interaction and should not
        return a result (it handles output directly).
        """
        pass

    def _prompt_user(self, message: str, default: bool = True) -> bool:
        """
        Prompt the user for confirmation.

        This is a helper method that can be overridden for testing.
        """
        import questionary

        return questionary.confirm(message, default=default).ask()

    def _select_option(self, message: str, choices: list[str]) -> Optional[str]:
        """
        Present a selection menu to the user.

        This is a helper method that can be overridden for testing.
        """
        import questionary

        return questionary.select(message, choices=choices).ask()


class NonInteractiveWorkflow(ABC):
    """
    Abstract base class for non-interactive workflows.

    Non-interactive workflows are pure functions that take inputs
    and return results. They are designed for CLI commands, scripts,
    and testing. They should never prompt the user.
    """

    @abstractmethod
    def run(self, **kwargs: Any) -> WorkflowResult:
        """
        Run the non-interactive workflow.

        Args:
            **kwargs: Workflow-specific parameters

        Returns:
            WorkflowResult with status and optional data
        """
        pass

    def _validate_inputs(self, **kwargs: Any) -> None:
        """
        Validate workflow inputs.

        Raises ValueError if inputs are invalid.
        This method can be overridden by subclasses.
        """
        pass

    def _get_defaults(self) -> Dict[str, Any]:
        """
        Get default values for workflow parameters.

        This method can be overridden by subclasses to provide
        sensible defaults when parameters are not provided.
        """
        return {}


class WorkflowAdapter:
    """
    Adapter that allows using a NonInteractiveWorkflow as an InteractiveWorkflow.

    This is useful for gradually migrating workflows to the new structure.
    """

    def __init__(self, non_interactive_workflow: NonInteractiveWorkflow):
        """
        Initialize adapter.

        Args:
            non_interactive_workflow: The non-interactive workflow to adapt
        """
        self.workflow = non_interactive_workflow

    def run(self) -> None:
        """Run the non-interactive workflow with interactive prompts for inputs."""
        import questionary
        from rich import print

        # Get default values
        defaults = self.workflow._get_defaults()

        # Prompt for required inputs (this is a simplified example)
        # Subclasses should override this to provide proper prompts
        inputs = {}
        for key, default_value in defaults.items():
            if isinstance(default_value, bool):
                inputs[key] = questionary.confirm(
                    f"{key.replace('_', ' ').title()}:", default=default_value
                ).ask()
            elif isinstance(default_value, (int, float)):
                inputs[key] = questionary.text(
                    f"{key.replace('_', ' ').title()}:", default=str(default_value)
                ).ask()
            else:
                inputs[key] = questionary.text(
                    f"{key.replace('_', ' ').title()}:",
                    default=str(default_value) if default_value else None,
                ).ask()

        # Run the workflow
        result = self.workflow.run(**inputs)

        # Handle result
        if result.is_success:
            print(
                f"[green]✅ {result.message or 'Workflow completed successfully'}[/green]"
            )
        elif result.is_cancelled:
            print(f"[yellow]⚠️ {result.message or 'Workflow cancelled'}[/yellow]")
        elif result.requires_interaction:
            print(
                f"[yellow]⚠️ {result.message or 'Workflow requires interaction'}[/yellow]"
            )
        else:
            print(f"[red]❌ {result.message or 'Workflow failed'}[/red]")
