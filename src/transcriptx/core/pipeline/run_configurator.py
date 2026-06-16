from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from transcriptx.core.config import strip_activation_keys_from_nested_map
from transcriptx.core.config.persistence import (
    CONFIG_SCHEMA_VERSION,
    clear_draft_override,
    compute_config_hash,
    load_draft_override,
    load_project_config,
    save_run_effective,
    save_run_override,
)
from transcriptx.core.config.resolver import resolve_effective_config
from transcriptx.core.config.validation import validate_config
from transcriptx.core.pipeline.contracts import RunConfigSnapshot
from transcriptx.core.utils.config import set_config


@dataclass
class ConfigResolution:
    config: Any
    snapshot: RunConfigSnapshot
    draft_override: Dict[str, Any] | None


class RunConfigurator:
    def resolve_and_apply(self, run_dir: Path) -> ConfigResolution:
        draft_override = load_draft_override()
        applied_draft = False
        if draft_override:
            save_run_override(
                run_dir, strip_activation_keys_from_nested_map(draft_override)
            )
            applied_draft = True

        resolved = resolve_effective_config(run_dir=run_dir)
        validation_errors = validate_config(resolved.effective_dict_nested)
        if validation_errors:
            error_lines = []
            for key, errors in validation_errors.items():
                for err in errors:
                    error_lines.append(f"{key}: {err.message}")
            raise ValueError(
                "Configuration validation failed before run:\n" + "\n".join(error_lines)
            )

        save_run_effective(run_dir, resolved.effective_dict_nested)
        config_hash = compute_config_hash(resolved.effective_dict_nested)
        config_source = "default"
        if draft_override:
            config_source = "run_override"
        else:
            if load_project_config():
                config_source = "project"

        set_config(resolved.effective_config)
        snapshot = RunConfigSnapshot(
            config_hash=config_hash,
            config_source=config_source,
            draft_override_applied=applied_draft,
            schema_version=CONFIG_SCHEMA_VERSION,
        )
        return ConfigResolution(
            config=resolved.effective_config,
            snapshot=snapshot,
            draft_override=draft_override,
        )

    def clear_draft_override(self, should_clear: bool) -> None:
        if should_clear:
            clear_draft_override()
