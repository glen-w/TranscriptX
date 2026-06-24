"""Block availability checks against artifact manifest."""

from __future__ import annotations

from dataclasses import dataclass

from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.specs import BlockPrereq, BlockSpec


@dataclass(frozen=True)
class BlockAvailability:
    available: bool
    reason: str | None
    matched_artifacts: tuple[str, ...]


def check_block_availability(spec: BlockSpec, ctx: BlockContext) -> BlockAvailability:
    if spec.prerequisites == BlockPrereq.RUN_SCOPED:
        if ctx.run_root is None or not ctx.run_id:
            return BlockAvailability(
                available=False,
                reason="Select a subject and run to view this block.",
                matched_artifacts=(),
            )

    if not spec.module_deps and not spec.artifact_patterns and not spec.artifact_kinds:
        return BlockAvailability(available=True, reason=None, matched_artifacts=())

    matched: list[str] = []
    for artifact in ctx.artifacts:
        if spec.module_deps and (artifact.module or "") not in spec.module_deps:
            continue
        if spec.artifact_kinds:
            kind_ok = artifact.kind in spec.artifact_kinds or any(
                artifact.kind.startswith(f"{k}") for k in spec.artifact_kinds
            )
            if not kind_ok:
                continue
        if spec.artifact_patterns and not any(
            artifact.rel_path.endswith(pat) for pat in spec.artifact_patterns
        ):
            continue
        matched.append(artifact.id)

    requires_match = bool(
        spec.module_deps or spec.artifact_patterns or spec.artifact_kinds
    )
    if requires_match and not matched:
        deps = ", ".join(spec.module_deps) if spec.module_deps else "artifacts"
        patterns = ", ".join(spec.artifact_patterns) if spec.artifact_patterns else ""
        detail = f" ({patterns})" if patterns else ""
        return BlockAvailability(
            available=False,
            reason=f"No matching artifacts for {deps}{detail}. Run the required analysis modules.",
            matched_artifacts=(),
        )

    return BlockAvailability(
        available=True, reason=None, matched_artifacts=tuple(matched)
    )
