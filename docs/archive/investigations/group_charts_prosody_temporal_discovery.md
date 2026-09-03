> **Archived / superseded.** Historical context only. Current authority: [group_charts_prosody_temporal_contract.md](../../groups/group_charts_prosody_temporal_contract.md). Do not treat as live roadmap or support policy.

# Discovery: group prosody temporal overlay (Phase 9 gate)

**Status:** Gate **satisfied** — v1 segment artifact path and contract are locked in [`group_charts_prosody_segment_artifact_v1.md`](group_charts_prosody_segment_artifact_v1.md). `prosody_dashboard` emits `{base_name}_prosody_overlay_segments.v1.json` under `prosody_dashboard/data/global/`.

## Gate (all required)

1. **Deterministic artifact path** — Resolved from member `output_dir` + `base_name` without heuristic search.
2. **Start seconds** — Documented per-point field for session-relative time (same family as other group temporal contracts).
3. **One fixed y-field** — Single documented metric; no ad-hoc numeric column picking.
4. **Stable semantics across runs** — Field meaning is stable for module versions covered by the contract.
5. **Versioned / documented output contract** — New or adopted artifact includes schema version or namespace for review and tooling.

## Implementation notes

- Overlay reader and tier-2 chart contract: [`group_charts_prosody_temporal_contract.md`](group_charts_prosody_temporal_contract.md).
- **y** for v1: raw **`rms_db`** per segment (see segment artifact doc).
