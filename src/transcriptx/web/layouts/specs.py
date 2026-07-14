"""Pydantic layout profile schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from transcriptx.web.blocks.placement import BlockPlacement

SUPPORTED_LAYOUT_PAGES = frozenset(
    {"overview", "insights", "charts", "dashboard_builder"}
)
# Bumped for optional placement.section field (Insights local navigation).
CURRENT_LAYOUT_SCHEMA_VERSION = 2

INSIGHTS_SECTIONS = frozenset(
    {"summary", "speakers", "actions", "highlights", "analysis"}
)

LayoutSection = Literal["summary", "speakers", "actions", "highlights", "analysis"]


class BlockPlacementModel(BaseModel):
    placement_id: str
    block_id: str
    title_override: str | None = None
    visible: bool = True
    params: dict[str, Any] = Field(default_factory=dict)
    section: str | None = None

    @field_validator("section")
    @classmethod
    def known_section(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in INSIGHTS_SECTIONS:
            raise ValueError(
                f"Unsupported section {value!r}; expected one of {sorted(INSIGHTS_SECTIONS)}"
            )
        return value

    def to_placement(self) -> BlockPlacement:
        return BlockPlacement(
            placement_id=self.placement_id,
            block_id=self.block_id,
            title_override=self.title_override,
            visible=self.visible,
            params=dict(self.params),
            section=self.section,
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
        # Accept v1 (no section) and v2 (section field).
        if value not in (1, CURRENT_LAYOUT_SCHEMA_VERSION):
            raise ValueError(
                f"Unsupported schema_version {value}; expected 1 or {CURRENT_LAYOUT_SCHEMA_VERSION}"
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
