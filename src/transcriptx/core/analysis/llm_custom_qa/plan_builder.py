"""Build UnroutedCustomQAPlan (requires v2 activation)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from transcriptx.core.analysis.llm_custom_qa.evidence_catalog import (
    catalog_version,
    expand_evidence_pack_ids,
    load_evidence_snapshots,
)
from transcriptx.core.analysis.llm_custom_qa.plan import (
    UnroutedCustomQAPlan,
    assert_v2_execution_allowed,
)
from transcriptx.core.analysis.llm_custom_qa.question_identity import (
    questions_hash_for_canonical,
)
from transcriptx.core.analysis.llm_custom_qa.resolve import EffectiveCustomQAQuestions
from transcriptx.core.analysis.llm_custom_qa.versioning import (
    SCHEDULER_VERSION,
    SPEAKER_ELIGIBILITY_POLICY_VERSION,
    V2_CONTRACT_VERSION,
)
from transcriptx.core.analysis.llm_support.hashing import sha256_text
from transcriptx.core.analysis.llm_support.speakers import (
    collect_named_speaker_groups_for_llm,
    speaker_limit_for_cell_cap,
)


def build_unrouted_plan(
    *,
    effective: EffectiveCustomQAQuestions,
    settings: Any,
    segments: list[dict[str, Any]],
    runtime_flags: Mapping[str, Any],
    context: Any = None,
    run_root: Optional[Path] = None,
    model_id: str = "",
    effort: str = "high",
    global_transcript_text: str = "",
) -> UnroutedCustomQAPlan:
    assert_v2_execution_allowed()
    expanded = expand_evidence_pack_ids(getattr(settings, "evidence_pack_ids", None))
    snapshots = load_evidence_snapshots(
        enabled_pack_ids=expanded, context=context, run_root=run_root
    )
    per_speaker_count = sum(1 for q in effective.structured if q.scopes.per_speaker)
    limit = speaker_limit_for_cell_cap(
        max_eligible_speakers=int(getattr(settings, "max_eligible_speakers", 12)),
        max_speaker_question_cells=int(
            getattr(settings, "max_speaker_question_cells", 48)
        ),
        per_speaker_question_count=per_speaker_count,
    )
    groups = collect_named_speaker_groups_for_llm(
        segments, runtime_flags=dict(runtime_flags)
    )
    omitted = tuple(g["speaker_key"] for g in groups[limit:])
    selected = groups[:limit]
    speaker_keys = tuple(g["speaker_key"] for g in selected)
    speaker_display = {g["speaker_key"]: g["display_name"] for g in selected}
    speaker_grouping_keys = {
        g["speaker_key"]: tuple(str(x) for x in g["grouping_keys"]) for g in selected
    }
    speaker_fps = {
        g["speaker_key"]: sha256_text(
            "\n".join(str(s.get("text") or "") for s in g["segments"])
        )
        for g in selected
    }
    return UnroutedCustomQAPlan(
        questions=effective.structured,
        question_order=effective.question_order,
        questions_hash=questions_hash_for_canonical(effective.structured),
        expanded_pack_ids=expanded,
        snapshots=snapshots,
        include_transcript=bool(getattr(settings, "include_transcript", True)),
        routing_enabled=bool(getattr(settings, "routing_enabled", True)),
        max_packs_per_question=int(getattr(settings, "max_packs_per_question", 3)),
        speaker_keys=speaker_keys,
        speaker_display=speaker_display,
        speaker_grouping_keys=speaker_grouping_keys,
        speaker_limit=limit,
        speakers_omitted_by_cap=omitted,
        max_llm_calls_per_run=int(getattr(settings, "max_llm_calls_per_run", 16)),
        max_reasoning_chars=int(getattr(settings, "max_reasoning_chars", 600)),
        max_answer_chars=int(getattr(settings, "max_answer_chars", 800)),
        catalog_version=catalog_version(),
        contract_version=V2_CONTRACT_VERSION,
        scheduler_version=SCHEDULER_VERSION,
        eligibility_policy_version=SPEAKER_ELIGIBILITY_POLICY_VERSION,
        transcript_global_fingerprint=sha256_text(global_transcript_text),
        transcript_speaker_fingerprints=speaker_fps,
        model_id=model_id,
        effort=effort,
        resolved_from=effective.resolved_from,
    )
