"""Layout profile persistence and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from transcriptx.core.utils.paths import PROFILES_DIR
from transcriptx.web.blocks.registry import validate_block_id
from transcriptx.web.layouts.specs import (
    CURRENT_LAYOUT_SCHEMA_VERSION,
    LayoutSpec,
    SUPPORTED_LAYOUT_PAGES,
)

UI_LAYOUTS_DIR = PROFILES_DIR / "ui_layouts"
PRESETS_DIR = Path(__file__).resolve().parent / "presets"


class LayoutValidationError(ValueError):
    """Developer-facing layout validation failure."""


def _default_layouts_dir() -> Path:
    return UI_LAYOUTS_DIR


class LayoutProfileStore:
    @staticmethod
    def layouts_dir(base: Path | None = None) -> Path:
        return base if base is not None else _default_layouts_dir()

    @staticmethod
    def list_layouts(base: Path | None = None) -> list[str]:
        ids: set[str] = set()
        root = LayoutProfileStore.layouts_dir(base)
        if root.exists():
            ids.update(p.stem for p in root.glob("*.yaml"))
        if PRESETS_DIR.exists():
            ids.update(p.stem for p in PRESETS_DIR.glob("*.yaml"))
        return sorted(ids)

    @staticmethod
    def load_layout(layout_id: str, base: Path | None = None) -> LayoutSpec:
        root = LayoutProfileStore.layouts_dir(base)
        path = root / f"{layout_id}.yaml"
        if not path.exists():
            preset = PRESETS_DIR / f"{layout_id}.yaml"
            if preset.exists():
                path = preset
            else:
                raise FileNotFoundError(f"Layout not found: {layout_id}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise LayoutValidationError(f"Layout {layout_id} must be a mapping")
        return LayoutProfileStore.validate_layout_dict(raw)

    @staticmethod
    def save_layout(spec: LayoutSpec, base: Path | None = None) -> Path:
        LayoutProfileStore.validate_layout(spec)
        root = LayoutProfileStore.layouts_dir(base)
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{spec.id}.yaml"
        payload = spec.model_dump(mode="json")
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return path

    @staticmethod
    def validate_layout_dict(data: dict[str, Any]) -> LayoutSpec:
        try:
            spec = LayoutSpec.model_validate(data)
        except ValidationError as exc:
            raise LayoutValidationError(str(exc)) from exc
        LayoutProfileStore._validate_block_refs(spec)
        LayoutProfileStore._validate_params(spec)
        return spec

    @staticmethod
    def validate_layout(spec: LayoutSpec) -> None:
        if spec.schema_version != CURRENT_LAYOUT_SCHEMA_VERSION:
            raise LayoutValidationError(
                f"schema_version mismatch: {spec.schema_version}"
            )
        for page_key in spec.pages:
            if page_key not in SUPPORTED_LAYOUT_PAGES:
                raise LayoutValidationError(f"Unsupported page key: {page_key}")
        LayoutProfileStore._validate_block_refs(spec)
        LayoutProfileStore._validate_params(spec)

    @staticmethod
    def _validate_block_refs(spec: LayoutSpec) -> None:
        for page_key, page in spec.pages.items():
            seen: set[str] = set()
            for block in page.blocks:
                if block.placement_id in seen:
                    raise LayoutValidationError(
                        f"Duplicate placement_id '{block.placement_id}' on page '{page_key}'"
                    )
                seen.add(block.placement_id)
                try:
                    validate_block_id(block.block_id)
                except ValueError as exc:
                    raise LayoutValidationError(str(exc)) from exc

    @staticmethod
    def _validate_params(spec: LayoutSpec) -> None:
        from transcriptx.web.blocks.registry import get_block

        for page in spec.pages.values():
            for placement in page.blocks:
                block = get_block(placement.block_id)
                if block is None:
                    continue
                schema = block.params_schema or {}
                required = schema.get("required", [])
                properties = schema.get("properties", {})
                for key in required:
                    if key not in placement.params:
                        raise LayoutValidationError(
                            f"Block '{placement.block_id}' placement "
                            f"'{placement.placement_id}' missing required param '{key}'"
                        )
                for key in placement.params:
                    if key not in properties and properties:
                        raise LayoutValidationError(
                            f"Block '{placement.block_id}' placement "
                            f"'{placement.placement_id}' unsupported param '{key}'"
                        )
