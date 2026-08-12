"""Layout profile persistence and validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from transcriptx.core.utils.paths import PROFILES_DIR
from transcriptx.web.blocks.registry import validate_block_id
from transcriptx.web.layouts.specs import (
    CURRENT_LAYOUT_SCHEMA_VERSION,
    BlockPlacementModel,
    LayoutPageSpec,
    LayoutSpec,
    SUPPORTED_LAYOUT_PAGES,
)

UI_LAYOUTS_DIR = PROFILES_DIR / "ui_layouts"
PRESETS_DIR = Path(__file__).resolve().parent / "presets"
ALL_LAYOUT_ID = "all"
BUILTIN_LAYOUT_IDS = frozenset(
    {
        "default",
        "executive",
        "developer_debug",
        "meeting_followup",
        "speaker_focus",
        "minimal",
        ALL_LAYOUT_ID,
    }
)

_LAYOUT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


class LayoutValidationError(ValueError):
    """Developer-facing layout validation failure."""


def slugify_layout_id(raw: str) -> str:
    """Normalize a layout id to a safe filesystem stem.

    Raises LayoutValidationError when the result is empty or unsafe.
    """
    text = (raw or "").strip()
    if not text:
        raise LayoutValidationError("Layout id must be non-empty.")
    if "/" in text or "\\" in text or ".." in text:
        raise LayoutValidationError(
            "Layout id must not contain path separators or '..'."
        )
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", text).strip("_")
    if not slug or not _LAYOUT_ID_RE.match(slug):
        raise LayoutValidationError(
            "Layout id must start with a letter or digit and contain only "
            "letters, digits, underscores, or hyphens."
        )
    return slug


def _param_type_ok(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return True


def _default_layouts_dir() -> Path:
    return UI_LAYOUTS_DIR


def _build_all_layout() -> LayoutSpec:
    """Every registered block once per page, sorted by block_id."""
    from transcriptx.web.blocks.registry import list_blocks

    block_ids = sorted(spec.id for spec in list_blocks())
    pages: dict[str, LayoutPageSpec] = {}
    for page_id in ("overview", "insights", "charts"):
        pages[page_id] = LayoutPageSpec(
            page_id=page_id,
            blocks=[
                BlockPlacementModel(
                    placement_id=f"all_{page_id}_{block_id}",
                    block_id=block_id,
                    visible=True,
                )
                for block_id in block_ids
            ],
        )
    return LayoutSpec(
        schema_version=CURRENT_LAYOUT_SCHEMA_VERSION,
        id=ALL_LAYOUT_ID,
        title="All",
        description="Every registered view block in alphabetical order.",
        pages=pages,
    )


class LayoutProfileStore:
    @staticmethod
    def layouts_dir(base: Path | None = None) -> Path:
        return base if base is not None else _default_layouts_dir()

    @staticmethod
    def is_builtin(layout_id: str) -> bool:
        return layout_id in BUILTIN_LAYOUT_IDS

    @staticmethod
    def custom_layout_path(layout_id: str, base: Path | None = None) -> Path:
        slug = slugify_layout_id(layout_id)
        return LayoutProfileStore.layouts_dir(base) / f"{slug}.yaml"

    @staticmethod
    def custom_layout_exists(layout_id: str, base: Path | None = None) -> bool:
        try:
            return LayoutProfileStore.custom_layout_path(layout_id, base).exists()
        except LayoutValidationError:
            return False

    @staticmethod
    def list_layouts(base: Path | None = None) -> list[str]:
        ids: set[str] = {ALL_LAYOUT_ID}
        root = LayoutProfileStore.layouts_dir(base)
        if root.exists():
            ids.update(p.stem for p in root.glob("*.yaml"))
        if PRESETS_DIR.exists():
            ids.update(p.stem for p in PRESETS_DIR.glob("*.yaml"))
        return sorted(ids)

    @staticmethod
    def load_layout(layout_id: str, base: Path | None = None) -> LayoutSpec:
        if layout_id == ALL_LAYOUT_ID:
            spec = _build_all_layout()
            LayoutProfileStore.validate_layout(spec)
            return spec
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
    def save_layout(
        spec: LayoutSpec,
        base: Path | None = None,
        *,
        overwrite: bool = True,
    ) -> Path:
        slug = slugify_layout_id(spec.id)
        if LayoutProfileStore.is_builtin(slug):
            raise LayoutValidationError(
                f"Built-in layout '{slug}' is immutable. Save as a custom layout id."
            )
        if slug != spec.id:
            raise LayoutValidationError(
                f"Layout id '{spec.id}' is not a valid slug; use '{slug}'."
            )
        LayoutProfileStore.validate_layout(spec)
        root = LayoutProfileStore.layouts_dir(base)
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{slug}.yaml"
        if path.exists() and not overwrite:
            raise LayoutValidationError(
                f"Custom layout '{slug}' already exists. Pass overwrite=True to replace it."
            )
        payload = spec.model_dump(mode="json")
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return path

    @staticmethod
    def save_as_custom(
        source: LayoutSpec,
        new_id: str,
        *,
        title: str | None = None,
        base: Path | None = None,
        overwrite: bool = True,
    ) -> Path:
        """Clone a layout (including builtins) into a custom user layout."""
        slug = slugify_layout_id(new_id)
        if LayoutProfileStore.is_builtin(slug):
            raise LayoutValidationError(
                f"Cannot use built-in id '{slug}' for a custom layout."
            )
        cloned = source.model_copy(
            update={
                "id": slug,
                "title": title or slug,
                "schema_version": CURRENT_LAYOUT_SCHEMA_VERSION,
            }
        )
        return LayoutProfileStore.save_layout(cloned, base=base, overwrite=overwrite)

    @staticmethod
    def delete_custom(layout_id: str, base: Path | None = None) -> Path:
        """Delete a custom layout YAML. Built-ins cannot be deleted."""
        slug = slugify_layout_id(layout_id)
        if LayoutProfileStore.is_builtin(slug):
            raise LayoutValidationError(
                f"Built-in layout '{slug}' cannot be deleted."
            )
        path = LayoutProfileStore.custom_layout_path(slug, base)
        if not path.exists():
            raise FileNotFoundError(f"Custom layout not found: {slug}")
        path.unlink()
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
                for key, value in placement.params.items():
                    if key not in properties and properties:
                        raise LayoutValidationError(
                            f"Block '{placement.block_id}' placement "
                            f"'{placement.placement_id}' unsupported param '{key}'"
                        )
                    prop = properties.get(key) if properties else None
                    if not isinstance(prop, dict):
                        continue
                    expected = prop.get("type")
                    if isinstance(expected, str) and not _param_type_ok(
                        value, expected
                    ):
                        raise LayoutValidationError(
                            f"Block '{placement.block_id}' placement "
                            f"'{placement.placement_id}' param '{key}' "
                            f"must be type '{expected}'"
                        )
