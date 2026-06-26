"""Registry of Pydantic config pilots and shared bridge helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Type

from pydantic import BaseModel

from transcriptx.core.utils.config.analysis import ActsConfig, SemanticSimilarityV2Config
from transcriptx.core.utils.config.system import LLMConfig
from transcriptx.core.utils.config.workflow import MetadataConfig

from .models.acts import ActsSettingsModel
from .models.dashboard_display import DashboardDisplaySettingsModel
from .models.llm import LLMSettingsModel
from .models.metadata import MetadataSettingsModel
from .models.semantic_similarity_v2 import SemanticSimilarityV2SettingsModel
from .pydantic_registry import (
    pydantic_model_to_field_metadata,
    serialize_field_metadata,
)
from .registry import FieldMetadata

SEMANTIC_SIMILARITY_V2_PREFIX = "analysis.semantic_similarity_v2"


@dataclass(frozen=True)
class PydanticPilotSpec:
    """One incrementally migrated config subtree backed by Pydantic."""

    pilot_id: str
    model: Type[BaseModel]
    dotpath_prefix: str
    category: str = ""
    dataclass_type: Type[Any] | None = None

    @property
    def dotpath_prefix_with_dot(self) -> str:
        return f"{self.dotpath_prefix}."


def _category_for(spec: PydanticPilotSpec) -> str:
    if spec.category:
        return spec.category
    if "." in spec.dotpath_prefix:
        return spec.dotpath_prefix.split(".", 1)[0]
    return spec.dotpath_prefix


PYDANTIC_REGISTRY_PILOTS: tuple[PydanticPilotSpec, ...] = (
    PydanticPilotSpec(
        pilot_id="semantic_similarity_v2",
        model=SemanticSimilarityV2SettingsModel,
        dotpath_prefix=SEMANTIC_SIMILARITY_V2_PREFIX,
        category="analysis",
        dataclass_type=SemanticSimilarityV2Config,
    ),
    PydanticPilotSpec(
        pilot_id="metadata",
        model=MetadataSettingsModel,
        dotpath_prefix="metadata",
        category="metadata",
        dataclass_type=MetadataConfig,
    ),
    PydanticPilotSpec(
        pilot_id="dashboard_display",
        model=DashboardDisplaySettingsModel,
        dotpath_prefix="dashboard",
        category="dashboard",
        dataclass_type=None,
    ),
    PydanticPilotSpec(
        pilot_id="llm",
        model=LLMSettingsModel,
        dotpath_prefix="llm",
        category="llm",
        dataclass_type=LLMConfig,
    ),
    PydanticPilotSpec(
        pilot_id="acts",
        model=ActsSettingsModel,
        dotpath_prefix="analysis.acts",
        category="analysis",
        dataclass_type=ActsConfig,
    ),
)

PYDANTIC_VALIDATED_PREFIXES: tuple[str, ...] = tuple(
    spec.dotpath_prefix_with_dot for spec in PYDANTIC_REGISTRY_PILOTS
)


def pilot_field_names(spec: PydanticPilotSpec) -> frozenset[str]:
    return frozenset(spec.model.model_fields.keys())


def pilot_field_dotpath(spec: PydanticPilotSpec, field_name: str) -> str:
    return f"{spec.dotpath_prefix}.{field_name}"


def all_pydantic_field_dotpaths() -> frozenset[str]:
    keys: set[str] = set()
    for spec in PYDANTIC_REGISTRY_PILOTS:
        for name in spec.model.model_fields:
            keys.add(pilot_field_dotpath(spec, name))
    return frozenset(keys)


def find_pilot_for_dotpath_key(key: str) -> PydanticPilotSpec | None:
    for spec in PYDANTIC_REGISTRY_PILOTS:
        prefix = spec.dotpath_prefix_with_dot
        if not key.startswith(prefix):
            continue
        field_name = key[len(prefix) :]
        if field_name in spec.model.model_fields:
            return spec
    return None


def is_pydantic_validated_field_key(key: str) -> bool:
    return find_pilot_for_dotpath_key(key) is not None


def apply_pydantic_registry_overrides(registry: Dict[str, FieldMetadata]) -> None:
    """Overwrite registry entries for all registered Pydantic pilots."""
    for spec in PYDANTIC_REGISTRY_PILOTS:
        registry.update(
            pydantic_model_to_field_metadata(
                spec.model,
                dotpath_prefix=spec.dotpath_prefix,
                category=_category_for(spec),
            )
        )


def capture_pilot_schema_golden(spec: PydanticPilotSpec) -> Dict[str, Dict[str, Any]]:
    """Build serializable registry metadata for one pilot subtree."""
    metadata = pydantic_model_to_field_metadata(
        spec.model,
        dotpath_prefix=spec.dotpath_prefix,
        category=_category_for(spec),
    )
    return {
        key: serialize_field_metadata(meta) for key, meta in sorted(metadata.items())
    }


def extract_subtree_overrides(
    flattened: Dict[str, Any],
    spec: PydanticPilotSpec,
) -> Dict[str, Any]:
    return _extract_subtree_overrides(flattened, spec)


def _extract_subtree_overrides(
    flattened: Dict[str, Any],
    spec: PydanticPilotSpec,
) -> Dict[str, Any]:
    prefix = spec.dotpath_prefix_with_dot
    overrides: Dict[str, Any] = {}
    for key, value in flattened.items():
        if not key.startswith(prefix):
            continue
        field_name = key[len(prefix) :]
        if field_name in spec.model.model_fields:
            overrides[field_name] = value
    return overrides


def serialize_non_pydantic_registry_baseline(
    registry: Dict[str, FieldMetadata],
) -> Dict[str, Dict[str, Any]]:
    """Serialize registry keys that are not owned by any Pydantic pilot field."""
    pilot_keys = all_pydantic_field_dotpaths()
    return {
        key: serialize_field_metadata(meta)
        for key, meta in sorted(registry.items())
        if key not in pilot_keys
    }
