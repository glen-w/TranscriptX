"""Block availability checks against artifact manifest."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.group_content import is_group_run
from transcriptx.web.blocks.specs import BlockPrereq, BlockSpec


@dataclass(frozen=True)
class BlockAvailability:
    available: bool
    reason: str | None
    matched_artifacts: tuple[str, ...]


def _effective_module_deps(
    spec: BlockSpec, placement_params: Mapping[str, Any] | None
) -> tuple[str, ...]:
    """Placement params may narrow module_deps (e.g. llm_summary_block module=)."""
    if not placement_params:
        return spec.module_deps
    module = placement_params.get("module")
    if isinstance(module, str) and module and spec.module_deps:
        if module in spec.module_deps:
            return (module,)
    return spec.module_deps


def _effective_artifact_patterns(
    spec: BlockSpec, placement_params: Mapping[str, Any] | None
) -> tuple[str, ...]:
    if placement_params:
        stem = placement_params.get("artifact_stem")
        if isinstance(stem, str) and stem:
            return (f"{stem}.json", f"{stem}.md")
    return spec.artifact_patterns


def _missing_artifact_reason(
    *,
    deps: str,
    detail: str,
    run_root: Path | None,
) -> str:
    if run_root is not None and is_group_run(run_root):
        return (
            f"No matching artifacts for {deps}{detail}. "
            "Group rollups or member session outputs may still appear under "
            "Artifacts, or re-run group analysis with those modules selected."
        )
    return (
        f"No matching artifacts for {deps}{detail}. "
        "Run the required analysis modules."
    )


def check_block_availability(
    spec: BlockSpec,
    ctx: BlockContext,
    *,
    placement_params: Mapping[str, Any] | None = None,
) -> BlockAvailability:
    if spec.prerequisites == BlockPrereq.RUN_SCOPED:
        if ctx.run_root is None or not ctx.run_id:
            return BlockAvailability(
                available=False,
                reason="Select a subject and run to view this block.",
                matched_artifacts=(),
            )

    module_deps = _effective_module_deps(spec, placement_params)
    artifact_patterns = _effective_artifact_patterns(spec, placement_params)

    if not module_deps and not artifact_patterns and not spec.artifact_kinds:
        return BlockAvailability(available=True, reason=None, matched_artifacts=())

    matched: list[str] = []
    for artifact in ctx.artifacts:
        if module_deps and (artifact.module or "") not in module_deps:
            continue
        if spec.artifact_kinds:
            kind_ok = artifact.kind in spec.artifact_kinds or any(
                artifact.kind.startswith(f"{k}") for k in spec.artifact_kinds
            )
            if not kind_ok:
                continue
        if artifact_patterns and not any(
            artifact.rel_path.endswith(pat) for pat in artifact_patterns
        ):
            continue
        matched.append(artifact.id)

    requires_match = bool(module_deps or artifact_patterns or spec.artifact_kinds)
    if requires_match and not matched:
        deps = ", ".join(module_deps) if module_deps else "artifacts"
        patterns = ", ".join(artifact_patterns) if artifact_patterns else ""
        detail = f" ({patterns})" if patterns else ""
        return BlockAvailability(
            available=False,
            reason=_missing_artifact_reason(
                deps=deps, detail=detail, run_root=ctx.run_root
            ),
            matched_artifacts=(),
        )

    return BlockAvailability(
        available=True, reason=None, matched_artifacts=tuple(matched)
    )
