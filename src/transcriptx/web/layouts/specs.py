"""Pydantic layout profile schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from transcriptx.web.blocks.placement import BlockPlacement, GridSpec

SUPPORTED_LAYOUT_PAGES = frozenset({"overview", "insights", "dashboard_builder"})
CURRENT_LAYOUT_SCHEMA_VERSION = 1


class GridSpecModel(BaseModel):
    col: int = 0
    row: int = 0
    w: int = 12
    h: int = 1

    @field_validator("w", "h")
    @classmethod
    def positive_span(cls, value: int) -> int:
        if value < 1:
            raise ValueError("grid w and h must be >= 1")
        return value

    def to_grid_spec(self) -> GridSpec:
        return GridSpec(col=self.col, row=self.row, w=self.w, h=self.h)


class BlockPlacementModel(BaseModel):
    placement_id: str
    block_id: str
    title_override: str | None = None
    visible: bool = True
    params: dict[str, Any] = Field(default_factory=dict)
    grid: GridSpecModel | None = None

    def to_placement(self) -> BlockPlacement:
        return BlockPlacement(
            placement_id=self.placement_id,
            block_id=self.block_id,
            title_override=self.title_override,
            visible=self.visible,
            params=dict(self.params),
            grid=self.grid.to_grid_spec() if self.grid else None,
        )


class LayoutPageSpec(BaseModel):
    page_id: str
    blocks: list[BlockPlacementModel] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_placement_ids(self) -> "LayoutPageSpec":
        seen: set[str] = set()
        for block in self.blocks:
            if block.placement_id in seen:
                raise ValueError(f"Duplicate placement_id: {block.placement_id}")
            seen.add(block.placement_id)
        return self


class LayoutSpec(BaseModel):
    schema_version: int = CURRENT_LAYOUT_SCHEMA_VERSION
    id: str
    title: str
    description: str = ""
    pages: dict[str, LayoutPageSpec] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def supported_version(cls, value: int) -> int:
        if value != CURRENT_LAYOUT_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported schema_version {value}; expected {CURRENT_LAYOUT_SCHEMA_VERSION}"
            )
        return value

    @model_validator(mode="after")
    def validate_pages(self) -> "LayoutSpec":
        for page_key in self.pages:
            if page_key not in SUPPORTED_LAYOUT_PAGES:
                raise ValueError(f"Unsupported page key: {page_key}")
        return self

    def page_placements(self, page_id: str) -> list[BlockPlacement]:
        page = self.pages.get(page_id)
        if page is None:
            return []
        return [b.to_placement() for b in page.blocks]
