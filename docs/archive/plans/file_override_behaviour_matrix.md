> **Archived / superseded.** Historical context only. Current authority: [DEV_INDEX.md](../../DEV_INDEX.md). Do not treat as live roadmap or support policy.

# File-override behaviour matrix (Config ownership 1.7 / B0)

Captured 2026-07-20 from `file_overrides.load_config_file_into` + probe/pilot tests
**before** the atomic deep-candidate refactor. Do not change production apply semantics
without updating this matrix and characterization tests.

| Section / path | Precedence within file apply | Unknown keys | Partial merge | Replacement | Tuple coercion | Validation failure (pre-apply) | Validation failure (post-apply / nested) | Special notes |
|----------------|------------------------------|--------------|---------------|-------------|----------------|--------------------------------|------------------------------------------|---------------|
| Missing file | noop | n/a | n/a | n/a | n/a | n/a | n/a | Returns without error |
| Raw payload | `unwrap_config_payload` then `validate_raw_config_dict` | Unknown **top-level** → `ConfigLoadError` before apply | n/a | n/a | n/a | Blocks all apply | n/a | Allowlist in `config_raw_validation` |
| `analysis.*` flat attrs | setattr when hasattr | Silently skipped if not hasattr | Partial keys only | Scalar replace | n/a | Pre-apply raw | Nested `validate()` if present | |
| `analysis.<nested>` in `_NESTED_ANALYSIS_SUBTREES` | Recursive dataclass apply | Unknown nested keys skipped | Partial nested update | Lists replace; dict fields shallow `{**cur,**new}` | Length-2 numeric lists → tuple | Pre-apply raw | Nested `validate()` after subtree | Adapter-owned length-2 targets skipped here |
| Adapter-owned `analysis.<target>` | Deferred to adapter loop | Via adapter | Via `apply_profile_to_config` | Adapter semantics | Adapter | Pre-apply raw | Adapter / later validate | Skipped in nested loop |
| `analysis.quality_filtering_profiles` | Deferred; applied last among analysis specials | Kept as-is (no Pydantic strip) | Whole-dict replace of profiles map | Whole dict replace | Threshold length-2 lists → tuples | Pre-apply raw | None specific | After adapters |
| `input` / `output` / `logging` / `audio_preprocessing` / `group_analysis` | Flat setattr loop | Skipped if not hasattr | Partial | Scalar/attr replace | n/a | Pre-apply raw | Via later `validate_config` consumers | Pilots cover partial merge |
| `dashboard` / `metadata` / `llm` | Flat setattr if dict section | Skipped if not hasattr | Partial | Replace | n/a | Pre-apply raw | Later validate | |
| `workflow` non-`speaker_gate` | `apply_profile_to_config(workflow, {key: value})` | Profile apply rules | Per-key | Profile apply | Profile | Pre-apply raw | Profile validate | |
| `workflow.speaker_gate` | `apply_profile_to_config(speaker_gate, value)` | Profile apply rules | Nested partial | Profile apply | Profile | Pre-apply raw | Profile validate | Dedicated branch |
| Root `use_emojis` / `core_mode` | bool() coerce | n/a | n/a | Replace | n/a | Pre-apply raw | n/a | Applied after quality profiles |
| Apply order | base sections → adapters → quality profiles → root bools | | | | | | | Documented in code comments |

## Atomicity (pre-1.7)

Historically mutations applied **in place** on the live config. A mid-apply failure could leave partial state. Wave 0 B1 requires deep independent candidate → validate complete → commit on success only.
