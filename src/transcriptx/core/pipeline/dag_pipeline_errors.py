"""Pipeline setup/error types for DAG construction."""


class PipelineSetupError(RuntimeError):
    """Raised when DAG execute_pipeline is called without required injected context."""
