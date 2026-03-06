"""Shared configuration registry and resolution utilities."""

from .registry import (
    FieldMetadata,
    flatten,
    unflatten,
    build_registry,
    get_default_config_dict,
)
from .resolver import ResolvedConfig, resolve_effective_config
from .persistence import (
    CONFIG_SCHEMA_VERSION,
    compute_config_hash,
    get_project_config_path,
    get_draft_override_path,
    get_run_override_path,
    get_run_effective_path,
    load_project_config,
    save_project_config,
    load_draft_override,
    save_draft_override,
    clear_draft_override,
    load_run_override,
    save_run_override,
    load_run_effective,
    save_run_effective,
)
from .validation import ValidationError, validate_config

__all__ = [
    "FieldMetadata",
    "ResolvedConfig",
    "ValidationError",
    "CONFIG_SCHEMA_VERSION",
    "build_registry",
    "clear_draft_override",
    "compute_config_hash",
    "flatten",
    "get_default_config_dict",
    "get_draft_override_path",
    "get_project_config_path",
    "get_run_effective_path",
    "get_run_override_path",
    "load_draft_override",
    "load_project_config",
    "load_run_effective",
    "load_run_override",
    "resolve_effective_config",
    "save_draft_override",
    "save_project_config",
    "save_run_effective",
    "save_run_override",
    "unflatten",
    "validate_config",
]
