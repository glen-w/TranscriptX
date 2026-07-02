"""Contract tests for module registry definition composition."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.domain.module_requirements import Requirement
from transcriptx.core.pipeline.module_registry_specs import (
    MODULE_CLASS_MAP,
    build_module_definitions,
)
from transcriptx.core.pipeline.module_specs import (
    MODULE_REGISTRY_ORDER,
    build_all_module_definitions,
)
from transcriptx.core.pipeline.module_specs.conversation import (
    build_conversation_module_definitions,
)
from transcriptx.core.pipeline.module_specs.core import build_core_module_definitions
from transcriptx.core.pipeline.module_specs.exports import (
    build_exports_module_definitions,
)
from transcriptx.core.pipeline.module_specs.nlp import build_nlp_module_definitions
from transcriptx.core.pipeline.module_specs.qa import build_qa_module_definitions
from transcriptx.core.pipeline.module_specs.speakers import (
    build_speakers_module_definitions,
)
from transcriptx.core.pipeline.module_specs.summary import (
    build_summary_module_definitions,
)
from transcriptx.core.pipeline.module_specs.topics import (
    build_topics_module_definitions,
)

from .module_registry_snapshot_utils import load_snapshot_fixture, merge_fragments

_MODULE_SPECS_DIR = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "transcriptx"
    / "core"
    / "pipeline"
    / "module_specs"
)

_DOMAIN_BUILDERS = (
    build_core_module_definitions,
    build_conversation_module_definitions,
    build_nlp_module_definitions,
    build_topics_module_definitions,
    build_exports_module_definitions,
    build_qa_module_definitions,
    build_summary_module_definitions,
    build_speakers_module_definitions,
)

_DEFAULT_REQUIREMENTS = [Requirement.SEGMENTS]


def _all_domain_fragments() -> dict[str, dict]:
    return merge_fragments(
        *(builder(_DEFAULT_REQUIREMENTS) for builder in _DOMAIN_BUILDERS)
    )


def test_module_ids_are_unique() -> None:
    seen: set[str] = set()
    for builder in _DOMAIN_BUILDERS:
        fragment = builder(_DEFAULT_REQUIREMENTS)
        overlap = seen & set(fragment)
        assert not overlap, f"duplicate module ids: {sorted(overlap)}"
        seen |= set(fragment)


def test_domain_fragments_cover_registry_order() -> None:
    merged = _all_domain_fragments()
    assert set(merged) == set(MODULE_REGISTRY_ORDER)
    assert len(merged) == len(MODULE_REGISTRY_ORDER)


def test_domain_fragments_have_no_missing_ids() -> None:
    merged = _all_domain_fragments()
    missing = set(MODULE_REGISTRY_ORDER) - set(merged)
    assert not missing, f"missing module ids: {sorted(missing)}"


def test_domain_fragments_have_no_extra_ids() -> None:
    merged = _all_domain_fragments()
    extra = set(merged) - set(MODULE_REGISTRY_ORDER)
    assert not extra, f"extra module ids: {sorted(extra)}"


def test_every_fragment_id_in_snapshot() -> None:
    snapshot = load_snapshot_fixture()
    merged = _all_domain_fragments()
    extra = set(merged) - set(snapshot["modules"])
    assert not extra, f"fragment ids not in snapshot: {sorted(extra)}"


def test_every_snapshot_id_in_exactly_one_fragment() -> None:
    snapshot = load_snapshot_fixture()
    merged = _all_domain_fragments()
    assert set(merged) == set(snapshot["modules"])
    assert len(merged) == len(snapshot["modules"]) == len(snapshot["module_order"])


def test_dependencies_reference_known_modules() -> None:
    definitions = build_module_definitions(_DEFAULT_REQUIREMENTS)
    known = set(definitions)
    for module_id, spec in definitions.items():
        for dep in spec.get("dependencies", []):
            assert dep in known, f"{module_id} depends on unknown module {dep!r}"


def test_registry_order_matches_snapshot() -> None:
    snapshot = load_snapshot_fixture()
    raw = build_module_definitions(_DEFAULT_REQUIREMENTS)
    assert list(raw.keys()) == snapshot["module_order"]


def test_module_registry_order_matches_order_tuple() -> None:
    raw = build_all_module_definitions(_DEFAULT_REQUIREMENTS)
    assert list(raw.keys()) == list(MODULE_REGISTRY_ORDER)


def test_module_registry_order_matches_snapshot_module_order() -> None:
    snapshot = load_snapshot_fixture()
    assert list(MODULE_REGISTRY_ORDER) == snapshot["module_order"]


def test_required_display_metadata_present() -> None:
    snapshot = load_snapshot_fixture()
    allowed_categories = {
        spec["category"] for spec in snapshot["modules"].values() if "category" in spec
    }
    definitions = build_module_definitions(_DEFAULT_REQUIREMENTS)
    for module_id, spec in definitions.items():
        description = spec.get("description")
        assert isinstance(description, str) and description.strip(), module_id
        category = spec.get("category")
        assert (
            category in allowed_categories
        ), f"{module_id}: category {category!r} not in {allowed_categories}"


def test_module_specs_has_no_web_imports() -> None:
    for path in sorted(_MODULE_SPECS_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "transcriptx.web" not in text, f"web import in {path}"


def test_module_class_map_keys_exist_in_definitions() -> None:
    definitions = build_module_definitions(_DEFAULT_REQUIREMENTS)
    for module_id in MODULE_CLASS_MAP:
        assert module_id in definitions, module_id
