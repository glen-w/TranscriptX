Type: PRODUCT
Authority: self

# Documentation inventory (1.0 / Phase 0A)

Planning matrix for repository documentation classification. Created under Phase 0A; actions are executed in follow-on PRs.

**Legend — action:** retain | merge | rewrite | move | archive | delete

**Legend — audience:** entry | user | contract | developer | historical | disposable

**Hosted nav:** yes = candidate for future RTD user/dev nav; no = internal; archive-only = discoverable via ARCHIVE_INDEX only.

## Summary counts

| Action | Count |
|--------|------:|
| archive | 29 |
| delete | 2 |
| move | 0 |
| retain | 99 |
| rewrite | 1 |

## High-priority authority conflicts

1. Dual roadmaps resolved: programme plan moved to `docs/dev/pre_release_roadmap_1_0.md`; `docs/ROADMAP.md` rewritten for 0.9→1.0 outcomes (Phase 0B).
2. Archive paradox resolved: `docs/archive/` is tracked with banners (no longer gitignored).
3. Missing `Type:`/`Authority:` headers addressed on retained live docs; archived files use archive banners.
4. Stocktake retargeted to 0.9→1.0 stabilisation (not Wave 3 as default next capacity).

## Inventory rows

| path | current purpose | authority/status | audience | freshness | overlap | action | destination | links to update | owner | hosted |
|------|-----------------|------------------|----------|-----------|---------|--------|-------------|-----------------|-------|--------|
| README.md | TranscriptX | competing | entry | dated | vs pre-release PRODUCT definition | rewrite | — | many | docs/PRODUCT.md (0B) | yes |
| CHANGELOG.md | Changelog | live | entry | current | — | retain | — | README | CHANGELOG.md | no |
| CONTRIBUTING.md | Contributing to TranscriptX | live | developer | current | — | retain | — | README | CONTRIBUTING.md | no |
| SECURITY.md | Security Policy | live | entry | current | — | retain | — | README | SECURITY.md | no |
| docs/dev/pre_release_roadmap_1_0.md | 0.9.x → 1.0 programme plan | live | developer | current | vs docs/ROADMAP.md (outcomes) | retain | moved from root `pre-release_roadmap.md` | README, ROADMAP, DEV_INDEX | self | no |
| archive/README.md | Archive | live | developer | current | canonical script archive policy | retain | — | script inventory | self | no |
| assets/README.md | TranscriptX Assets | live | developer | current | — | retain | — | — | self | no |
| scripts/README_test_analysis_assess.md | Test Analysis Assessment Script | stale | disposable | superseded | See inventory destination | delete | — | Update inbound links | docs/dev/run_performance.md | no |
| docs/ADR-IMPORT-ORCHESTRATION.md | ADR: Transcript Import Orchestration Architecture | live | developer | current | — | retain | — | ARCHITECTURE | self | no |
| docs/ARCHITECTURE.md | TranscriptX Architecture | live | developer | current | align wording in 0B | retain | — | README | self | yes |
| docs/CONTRACT_INDEX.md | Contract boundary map | live | contract | current | add PRODUCT pointer in 0B | retain | — | CONTRIBUTING | contracts | yes |
| docs/ROADMAP.md | Long-term product roadmap (1.x / 2.0 / deferred) | live | developer | current | vs pre-release_roadmap (short-term) | retain | — | README, stocktake | self | no |
| docs/TERMS.md | TranscriptX terminology index (non-authoritative) | live | user | current | — | retain | — | CONTRACT_INDEX | contracts | yes |
| docs/archive/PHASE0_INVENTORY.md | Phase 0: Design and Inventory | stale | historical | superseded | See inventory destination | archive | docs/archive/assessments/PHASE0_INVENTORY.md | Update inbound links | docs/dev/documentation_inventory_1_0.md | archive-only |
| docs/archive/assessment-2026-03-10.md | TranscriptX Codebase Assessment — 2026-03-10 | stale | historical | superseded | See inventory destination | archive | docs/archive/assessments/assessment-2026-03-10.md | Update inbound links | docs/dev/stocktake_2026-07-17.md | archive-only |
| docs/archive/convokit_dependency_conflict.md | ConvoKit dependency conflict (historical) | stale | historical | superseded | See inventory destination | archive | docs/archive/investigations/convokit_dependency_conflict.md | Update inbound links | docs/dev/dependency_audit.md | archive-only |
| docs/archive/scikit-learn-upgrade-assessment.md | Scikit-learn upgrade assessment (1.3 → ≥1.6 for BERTopic) | stale | historical | superseded | See inventory destination | archive | docs/archive/assessments/scikit-learn-upgrade-assessment.md | Update inbound links | docs/dev/dependency_audit.md | archive-only |
| docs/archive/sprint_archive.md | Sprint plan (archived backlog) | stale | historical | superseded | See inventory destination | archive | docs/archive/plans/sprint_archive.md | Update inbound links | docs/ROADMAP.md | archive-only |
| docs/config/config_knobs_refactor_plan.md | TranscriptX config knobs — stepwise refactor plan | stale | historical | superseded | See inventory destination | archive | docs/archive/plans/config_knobs_refactor_plan.md | Update inbound links | docs/developer_quickstart.md | archive-only |
| docs/config/config_ownership_collapse_plan.md | Config ownership collapse (locked scope) | stale | historical | superseded | See inventory destination | archive | docs/archive/plans/config_ownership_collapse_plan.md | Update inbound links | docs/developer_quickstart.md | archive-only |
| docs/config/dict_profile_stores_spike.md | Dictionary profile stores — design spike (Wave 8) | stale | historical | superseded | See inventory destination | archive | docs/archive/plans/dict_profile_stores_spike.md | Update inbound links | docs/developer_quickstart.md | archive-only |
| docs/config/pydantic_migration.md | Pydantic config migration checklist | stale | historical | superseded | See inventory destination | archive | docs/archive/plans/pydantic_migration.md | Update inbound links | docs/developer_quickstart.md | archive-only |
| docs/contracts/llm_feedback_v1.md | LLM feedback v1 (collect-only) | live | contract | current | — | retain | — | CONTRACT_INDEX | docs/contracts/llm_feedback_v1.md | yes |
| docs/contracts/output-contract-v1.md | Output Contract v1 | live | contract | current | — | retain | — | CONTRACT_INDEX | docs/contracts/output-contract-v1.md | yes |
| docs/contracts/speaker_profiles_v1.md | Speaker profiles v1 (Phase 1) | live | contract | current | — | retain | — | CONTRACT_INDEX | docs/contracts/speaker_profiles_v1.md | yes |
| docs/contracts/speaker_profiles_voice_v1.md | Speaker profiles — voice phase v1 (R2) | live | contract | current | — | retain | — | CONTRACT_INDEX | docs/contracts/speaker_profiles_voice_v1.md | yes |
| docs/dev/COMPLEXITY_GATES.md | Complexity and performance gates (pipeline / reporting) | live | developer | current | — | retain | — | DEV_INDEX | self | no |
| docs/dev/CONTRIBUTING.md | Contributing to TranscriptX | live | developer | current | — | retain | — | DEV_INDEX | ARCHITECTURE.md | no |
| docs/dev/analysis_module_backlog_2026-07-17.md | Analysis module backlog (ranked) — 2026-07-17 | live | developer | dated | Retarget in 0B | retain | — | DEV_INDEX | self | no |
| docs/dev/analysis_run_performance_assessment_2026-07-19.md | Assessing analysis-run performance (low custom code) | stale | historical | superseded | See inventory destination | archive | docs/archive/assessments/analysis_run_performance_assessment_2026-07-19.md | Update inbound links | docs/dev/run_performance.md | archive-only |
| docs/dev/bertopic_optional_module.md | BERTopic module | live | developer | current | — | retain | — | DEV_INDEX | self | no |
| docs/dev/bertopic_platform_evidence.md | bertopic_platform_evidence.md | stale | historical | superseded | See inventory destination | archive | docs/archive/investigations/bertopic_platform_evidence.md | Update inbound links | docs/dev/bertopic_optional_module.md | archive-only |
| docs/dev/chart_evidence_migration.md | Chart evidence sidecar migration | stale | historical | superseded | See inventory destination | archive | docs/archive/migrations/chart_evidence_migration.md | Update inbound links | docs/contracts/output-contract-v1.md | archive-only |
| docs/dev/competitive_inspiration_2026-07-22.md | Competitive inspiration — open-source + commercial transcript tools vs Transcrip | stale | disposable | superseded | See inventory destination | delete | — | Update inbound links | docs/dev/local_scratch.md | no |
| docs/dev/composition_platform.md | Composition platform | live | developer | current | — | retain | — | DEV_INDEX | ARCHITECTURE.md | no |
| docs/dev/dependency_audit.md | Dependency audit & CVE waiver policy | live | developer | current | — | retain | — | DEV_INDEX | self | no |
| docs/developer_quickstart.md | Developer Quick Start — TranscriptX | live | developer | current | — | retain | — | DEV_INDEX | ARCHITECTURE.md | no |
| docs/dev/emotion_family_calibration_protocol_2026-07-18.md | Emotion family threshold calibration protocol | live | developer | dated | — | retain | — | DEV_INDEX | self | no |
| docs/dev/emotion_family_contracts_2026-07-18.md | Emotion family contracts — 2026-07-18 | live | contract | current | — | retain | — | CONTRACT_INDEX | docs/dev/emotion_family_contracts_2026-07-18.md | yes |
| docs/dev/export_system_refactor_plan.md | TranscriptX Export System — Incremental Refactor Plan | stale | historical | superseded | See inventory destination | archive | docs/archive/plans/export_system_refactor_plan.md | Update inbound links | docs/DEV_INDEX.md | archive-only |
| docs/dev/file_override_behaviour_matrix.md | File-override behaviour matrix (Config ownership 1.7 / B0) | stale | historical | superseded | See inventory destination | archive | docs/archive/plans/file_override_behaviour_matrix.md | Update inbound links | docs/DEV_INDEX.md | archive-only |
| docs/dev/group_functionality_audit_2026-07-17.md | Group functionality audit — 2026-07-17 | stale | historical | superseded | See inventory destination | archive | docs/archive/assessments/group_functionality_audit_2026-07-17.md | Update inbound links | docs/groups/group_analysis_module_outputs.md | archive-only |
| docs/dev/gui_acceptance_residual_checklist.md | GUI acceptance — residual manual checklist | live | developer | current | — | retain | — | DEV_INDEX | self | no |
| docs/dev/maintenance_release_hygiene_2026-04-01.md | Release-hygiene cleanup — 2026-04-01 | stale | historical | superseded | See inventory destination | archive | docs/archive/assessments/maintenance_release_hygiene_2026-04-01.md | Update inbound links | docs/dev/release_governance.md | archive-only |
| docs/dev/output_conventions.md | Output conventions | live | developer | current | — | retain | — | DEV_INDEX | contracts/output-contract-v1.md | no |
| docs/dev/pipeline_contracts.md | Pipeline Contracts (Authoritative) | live | contract | current | — | retain | — | CONTRACT_INDEX | docs/dev/pipeline_contracts.md | yes |
| docs/dev/refactor_top3_index_2026-07-16.md | TranscriptX — Top 3 refactor plans (index) | stale | historical | superseded | See inventory destination | archive | docs/archive/plans/refactor_top3_index_2026-07-16.md | Update inbound links | docs/DEV_INDEX.md | archive-only |
| docs/dev/release_governance.md | Release governance (manual next-tag checklist) | live | developer | current | — | retain | — | DEV_INDEX | self | no |
| docs/dev/rename_corrections_compat_table.md | Rename + corrections orchestrator — compatibility table | stale | historical | superseded | See inventory destination | archive | docs/archive/migrations/rename_corrections_compat_table.md | Update inbound links | docs/runtime/STORAGE.md | archive-only |
| docs/dev/rename_corrections_orchestrator_split_plan.md | Rename + corrections orchestrator split — stepwise plan | stale | historical | superseded | See inventory destination | archive | docs/archive/plans/rename_corrections_orchestrator_split_plan.md | Update inbound links | docs/DEV_INDEX.md | archive-only |
| docs/dev/run_cleanup_refactor_contracts.md | Run cleanup refactor — frozen contracts (Phase 0) | stale | historical | superseded | See inventory destination | archive | docs/archive/plans/run_cleanup_refactor_contracts.md | Update inbound links | docs/run_outcome_contract.md | archive-only |
| docs/dev/run_cleanup_refactor_plan_assessment.md | RunCleanupService refactor plan — assessment & edits | stale | historical | superseded | See inventory destination | archive | docs/archive/assessments/run_cleanup_refactor_plan_assessment.md | Update inbound links | docs/run_outcome_contract.md | archive-only |
| docs/dev/run_outcome_model.md | Run outcome model (developer notes) | live | developer | current | — | retain | — | DEV_INDEX | ../run_outcome_contract.md | no |
| docs/dev/run_performance.md | Analysis-run performance telemetry | live | developer | current | — | retain | — | DEV_INDEX | self | no |
| docs/dev/shared_analysis_io_refactor_plan.md | Shared analysis I/O extraction (refined) | stale | historical | superseded | See inventory destination | archive | docs/archive/plans/shared_analysis_io_refactor_plan.md | Update inbound links | docs/DEV_INDEX.md | archive-only |
| docs/dev/shim_inventory.md | Compatibility shim inventory (2026-07-20) | stale | historical | superseded | See inventory destination | archive | docs/archive/assessments/shim_inventory.md | Update inbound links | docs/dev/release_governance.md | archive-only |
| docs/dev/speaker_profiles_reference_env_index_gate.md | Speaker profiles — reference-environment index gate (Stage 8) | live | developer | current | — | retain | — | DEV_INDEX | advisory | no |
| docs/dev/speaker_voice_match_index_gate.md | Speaker voice match — reference-environment index gate (Stage 9) | live | developer | current | — | retain | — | DEV_INDEX | advisory | no |
| docs/dev/stats_summary_surface_decision_2026-04-21.md | Stats Summary Surface Decision (PR0) | stale | historical | superseded | See inventory destination | archive | docs/archive/plans/stats_summary_surface_decision_2026-04-21.md | Update inbound links | docs/DEV_INDEX.md | archive-only |
| docs/dev/stocktake_2026-07-17.md | TranscriptX Codebase Stocktake — 2026-07-17 | live | developer | dated | Retarget in 0B | retain | — | DEV_INDEX | self | no |
| docs/dev/streamlit_ui_test_assessment_2026-07-18.md | Streamlit UI Testing Assessment | stale | historical | superseded | See inventory destination | archive | docs/archive/assessments/streamlit_ui_test_assessment_2026-07-18.md | Update inbound links | tests/README.md | archive-only |
| docs/dev/wave2_lexicon_linguistics_2026-07-23.md | Wave 2 lexicon linguistics — B6 + B7 | live | developer | dated | — | retain | — | DEV_INDEX | self | no |
| docs/dev/wave_b13_interaction_graphs_2026-07-23.md | Wave B13 — speaker interaction graphs | live | developer | dated | — | retain | — | DEV_INDEX | self | no |
| docs/dev/wave_b16_keyphrases_2026-07-24.md | Wave B16 — Keyphrases module + wordclouds deepen (2026-07-24) | live | developer | dated | — | retain | — | DEV_INDEX | self | no |
| docs/dev/web_blocks.md | Web blocks | live | developer | current | — | retain | — | DEV_INDEX | ARCHITECTURE.md | no |
| docs/dev/web_fragment_pr_audit_table.md | Web fragment / rerun audit (PR review aid) | stale | historical | superseded | See inventory destination | archive | docs/archive/assessments/web_fragment_pr_audit_table.md | Update inbound links | docs/dev/web_blocks.md | archive-only |
| docs/generated/cli.md | Web launcher and Python API | live | user | current | — | retain | — | USER_INDEX | ARCHITECTURE | yes |
| docs/generated/modules.md | Module Catalog | live | user | current | — | retain | — | USER_INDEX | ARCHITECTURE | yes |
| docs/groups/group_analysis_module_outputs.md | Group analysis: what each module produces | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_analysis_module_outputs.md | yes |
| docs/groups/group_charts_acts_pooled_contract.md | Acts group charts: pooled single view (audited) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_acts_pooled_contract.md | yes |
| docs/groups/group_charts_acts_temporal_contract.md | Contract: group aggregate acts temporal overlay (Tier 2) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_acts_temporal_contract.md | yes |
| docs/groups/group_charts_bertopic_pooled_contract.md | Group charts — bertopic pooled | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_bertopic_pooled_contract.md | yes |
| docs/groups/group_charts_contagion_pooled_contract.md | Contagion group charts: pooled single view (edge-pooled) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_contagion_pooled_contract.md | yes |
| docs/groups/group_charts_default_overview.md | Group charts: default overview vs gallery (operator guide) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_analysis_module_outputs.md | yes |
| docs/groups/group_charts_emotion_pooled_contract.md | Emotion group charts: pooled single view | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_emotion_pooled_contract.md | yes |
| docs/groups/group_charts_emotion_temporal_contract.md | Contract: group aggregate emotion temporal overlay (Tier 2) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_emotion_temporal_contract.md | yes |
| docs/groups/group_charts_entity_sentiment_pooled_contract.md | Entity sentiment group charts: pooled single view | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_entity_sentiment_pooled_contract.md | yes |
| docs/groups/group_charts_epistemic_markers_pooled_contract.md | Epistemic markers group charts: pooled single view | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_epistemic_markers_pooled_contract.md | yes |
| docs/groups/group_charts_interactions_equity_contract.md | Interactions semantics and turn-taking equity | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_interactions_equity_contract.md | yes |
| docs/groups/group_charts_interactions_pooled_contract.md | Interactions group charts: pooled single view | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_interactions_pooled_contract.md | yes |
| docs/groups/group_charts_keyphrases_pooled_contract.md | Keyphrases group charts: pooled single view | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_keyphrases_pooled_contract.md | yes |
| docs/groups/group_charts_ner_pooled_contract.md | NER group charts: pooled single view | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_ner_pooled_contract.md | yes |
| docs/groups/group_charts_pauses_temporal_contract.md | Contract: group aggregate pauses temporal overlay (Tier 2) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_pauses_temporal_contract.md | yes |
| docs/groups/group_charts_phase4_outcome_table.md | Phase 4: group generic chart curation — outcome table | stale | historical | superseded | See inventory destination | archive | docs/archive/assessments/group_charts_phase4_outcome_table.md | Update inbound links | docs/groups/group_charts_default_overview.md | archive-only |
| docs/groups/group_charts_politeness_pooled_contract.md | Politeness group charts: pooled single view | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_politeness_pooled_contract.md | yes |
| docs/groups/group_charts_prosody_segment_artifact_v1.md | Contract: prosody overlay segment artifact (v1) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_prosody_segment_artifact_v1.md | yes |
| docs/groups/group_charts_prosody_temporal_contract.md | Contract: group aggregate prosody temporal overlay (Tier 2) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_prosody_temporal_contract.md | yes |
| docs/groups/group_charts_prosody_temporal_discovery.md | Discovery: group prosody temporal overlay (Phase 9 gate) | stale | historical | superseded | See inventory destination | archive | docs/archive/investigations/group_charts_prosody_temporal_discovery.md | Update inbound links | docs/groups/group_charts_prosody_temporal_contract.md | archive-only |
| docs/groups/group_charts_relational_pooling_model.md | Relational pooling model (group charts) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_relational_pooling_model.md | yes |
| docs/groups/group_charts_semantic_motifs_contract.md | Group charts — semantic similarity motifs (B14) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_semantic_motifs_contract.md | yes |
| docs/groups/group_charts_sentiment_cross_session_contract.md | Contract: group aggregate sentiment cross-session speaker (gallery) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_sentiment_cross_session_contract.md | yes |
| docs/groups/group_charts_sentiment_temporal_contract.md | Contract: group aggregate sentiment temporal overlay (Tier 2) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_sentiment_temporal_contract.md | yes |
| docs/groups/group_charts_stats_cross_session_contract.md | Contract: group aggregate stats cross-session speaker (gallery) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_stats_cross_session_contract.md | yes |
| docs/groups/group_charts_stats_pooled_contract.md | Stats group charts: pooled single view (totals only) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_stats_pooled_contract.md | yes |
| docs/groups/group_charts_tics_pooled_contract.md | Tics group charts: pooled single view | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_tics_pooled_contract.md | yes |
| docs/groups/group_charts_topic_modeling_pooled_contract.md | Topic modeling group charts: pooled single view | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_topic_modeling_pooled_contract.md | yes |
| docs/groups/group_charts_topic_shift_temporal_contract.md | Contract: group aggregate topic_shift temporal overlay (Tier 2) | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_charts_topic_shift_temporal_contract.md | yes |
| docs/groups/group_llm_synthesis_contract.md | Group LLM synthesis contract | live | contract | current | — | retain | — | CONTRACT_INDEX / groups | docs/groups/group_llm_synthesis_contract.md | yes |
| docs/public_surfaces.md | Public surfaces contract | live | contract | current | — | retain | — | CONTRACT_INDEX | docs/public_surfaces.md | yes |
| docs/recipes/whisperx/README.md | WhisperX standalone (optional reference recipe) | live | user | current | — | retain | — | transcription.md | docs/runtime/transcription.md | yes |
| docs/recipes/whisper-webui/README.md | Whisper-WebUI Gradio (optional interoperability recipe) | live | user | current | — | retain | — | transcription.md | docs/runtime/transcription.md | yes |
| docs/recipes/whisper-webui/docker-compose.whisper-webui.yml | Whisper-WebUI recipe compose (localhost/CPU) | live | user | current | — | retain | — | whisper-webui README | docs/recipes/whisper-webui/README.md | yes |
| docs/run_outcome_contract.md | Run outcome contract | live | contract | current | — | retain | — | CONTRACT_INDEX | docs/run_outcome_contract.md | yes |
| docs/runtime/STORAGE.md | TranscriptX Storage Policy | live | contract | current | — | retain | — | CONTRACT_INDEX | docs/runtime/STORAGE.md | yes |
| docs/runtime/corrections-llm.md | Corrections Studio LLM discovery | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | docs/runtime/STORAGE.md | yes |
| docs/runtime/docker-efficiency-baseline.md | Docker efficiency baseline | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | runtime/docker.md | yes |
| docs/runtime/docker.md | Docker | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | runtime/STORAGE.md | yes |
| docs/runtime/epistemic_markers.md | Epistemic markers (`epistemic_markers`) | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | self | yes |
| docs/runtime/install_verification_matrix.md | Install verification matrix | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | docs/runtime/STORAGE.md | yes |
| docs/runtime/installation.md | Installation & Configuration | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | runtime/STORAGE.md | yes |
| docs/runtime/keyphrases.md | Keyphrases (`keyphrases`) | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | self | yes |
| docs/runtime/lexical_diversity.md | Lexical diversity analysis | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | runtime/STORAGE.md | yes |
| docs/runtime/llm.md | Local LLM integration (Ollama) | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | runtime/docker.md | yes |
| docs/runtime/models.md | Analysis models | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | runtime/STORAGE.md | yes |
| docs/runtime/politeness.md | Politeness markers (`politeness`) | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | self | yes |
| docs/runtime/topic_shift.md | Topic-shift (`topic_shift`) contracts — Wave 1 | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | self | yes |
| docs/runtime/transcript_quality.md | ASR confidence (`transcript_quality`) | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | self | yes |
| docs/runtime/transcription.md | Transcription (external workflow) | live | user | current | RUNTIME headers → GUIDE in 0A pass | retain | — | USER_INDEX | runtime/STORAGE.md | yes |
| docs/v0.1-canonical-contract.md | TranscriptX v0.1 canonical contract (short) | live | contract | current | — | retain | — | CONTRACT_INDEX | docs/v0.1-canonical-contract.md | yes |
| tests/README.md | TranscriptX tests: how to run locally | live | developer | current | — | retain | — | DEV_INDEX | tests/README.md | no |
| tests/TEST_SUITE_ASSESSMENT.md | Pytest Suite Assessment | stale | historical | superseded | See inventory destination | archive | docs/archive/assessments/TEST_SUITE_ASSESSMENT.md | Update inbound links | tests/README.md | archive-only |
| tests/contracts/README.md | Contract tests (offline + deterministic) | live | developer | current | — | retain | — | DEV_INDEX | tests/README.md | no |
| tests/quarantine/README.md | Quarantined tests | live | developer | current | — | retain | — | DEV_INDEX | tests/README.md | no |
| tests/fixtures/emotion_family/characterization/README.md | Emotion-family characterization fixtures | live | developer | current | — | retain | — | DEV_INDEX | tests/README.md | no |
| .cursor/commands/*.md (11 files) | Maintainer agent playbooks | live | developer | current | Not user nav; backup.md has machine paths | retain | — | — | maintainer | no |
| docs/index.md | Sphinx landing + curated toctrees | live | entry | current | Hosted docs root (**0.9.5**) | retain | — | conf.py | docs/PRODUCT.md | yes |
| docs/dev/analysis_quality_audit_scaffold.md | Generated quality-audit registry rows | live | developer | current | Regen via `make docs-gen` | retain | — | analysis_quality_audit.md | analysis_quality_audit.md | no |
| docs/dev/analysis_quality_audit_judgements.md | Provisional Recommendation / Severity overlay (**0.9.7**) | live | developer | current | Owner sign-off open | retain | — | analysis_quality_audit.md, release_severity | analysis_quality_audit.md | no |
| docs/dev/rtd_go_live_checklist.md | RTD go-live flip steps | live | developer | current | Hostname denylist until slug | retain | — | docs_architecture | docs_architecture_1_0.md | no |
| docs/dev/ui_presentation_modes.md | Guided / Full (0.9.6 trial) | — | — | — | **removed** — trialled and decided against | deleted | — | pre_release_roadmap §16 | PRODUCT.md | no |
| docs/dev/demo_project.md | Demo project (0.9.6 trial) | — | — | — | **removed** — trialled and decided against | deleted | — | pre_release_roadmap §16 | PRODUCT.md | no |
| docs/dev/manual_acceptance_1_0.md | Human acceptance checklist skeleton | live | product | current | Human-testing wave | retain | — | pre_release_roadmap | release_severity_triage_1_0.md | no |
| docs/dev/overview_presentation_0_9_9.md | 0.9.9 Overview/results presentation polish backlog | live | product | current | After maintainer; before unfamiliar-user | retain | — | pre_release_roadmap, ROADMAP | manual_acceptance_1_0.md | no |
| website/ | Modest public landing + Pages | live | entry | current | Marketing; BMC placeholder | retain | — | README, ROADMAP | PRODUCT.md | no |
| NOTICE | Third-party model/dataset notice draft | live | entry | current | Hub-card owner-verify open | retain | — | trust_privacy, README | trust_privacy_model_governance_1_0.md | no |
| docs/requirements.txt | Sphinx/RTD install pins | live | developer | current | Mirrors `[docs]` extras | retain | — | .readthedocs.yml | docs_architecture_1_0.md | no |
| .readthedocs.yml | RTD build scaffold | live | developer | current | Hostname denylist until go-live | retain | — | docs_architecture | docs_architecture_1_0.md | no |

## Execution notes

- Contracts stay in place (no cosmetic directory moves).
- Archive layout: `docs/archive/{assessments,plans,investigations,migrations}/` plus `ARCHIVE_INDEX.md`.
- Script archive remains `archive/scripts/` (see `script_inventory_1_0.md`).
- Fixture expected-output markdown under `tests/fixtures/expected_outputs/` is excluded (test data, not product docs).

